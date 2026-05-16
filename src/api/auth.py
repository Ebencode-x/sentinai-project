"""Phase 2 — Multi-tenant API key authentication.

Tenant model
------------
Each tenant has:
  - A unique API key (opaque, random, 32-byte hex)
  - A name (for audit logs)
  - A rate-limit tier: "standard" | "premium" | "internal"

Key storage
-----------
Keys are loaded from the environment variable SENTINAI_API_KEYS as a
JSON object mapping key → tenant config, e.g.:

    SENTINAI_API_KEYS='{
        "sk-abc123...": {"name": "acme-corp", "tier": "standard"},
        "sk-def456...": {"name": "internal", "tier": "internal"}
    }'

Falls back to the legacy SENTINAI_API_KEY single-key env var for
backward compatibility with existing deployments.

Backward compatibility
----------------------
If SENTINAI_API_KEYS is not set but SENTINAI_API_KEY is set, a single
synthetic tenant "default" is created with tier "standard".
If neither is set, auth is disabled (dev/demo mode — logs a warning).
"""

from __future__ import annotations

import json
import logging
import os
import secrets
from dataclasses import dataclass, field
from enum import StrEnum
from typing import ClassVar

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

_API_KEY_HEADER_NAME = "X-API-Key"
_api_key_header = APIKeyHeader(name=_API_KEY_HEADER_NAME, auto_error=False)


# ---------------------------------------------------------------------------
# Tenant model
# ---------------------------------------------------------------------------


class RateLimitTier(StrEnum):
    STANDARD = "standard"  # 60 req/min
    PREMIUM = "premium"  # 300 req/min
    INTERNAL = "internal"  # unlimited


# Requests per minute per tier
TIER_LIMITS: dict[RateLimitTier, int | None] = {
    RateLimitTier.STANDARD: 60,
    RateLimitTier.PREMIUM: 300,
    RateLimitTier.INTERNAL: None,  # None = unlimited
}


@dataclass(frozen=True)
class Tenant:
    """Immutable tenant descriptor attached to every authenticated request."""

    name: str
    tier: RateLimitTier = RateLimitTier.STANDARD
    # Additional metadata — extend as needed
    metadata: dict = field(default_factory=dict)

    @property
    def rate_limit(self) -> int | None:
        """Requests per minute allowed for this tenant. None = unlimited."""
        return TIER_LIMITS[self.tier]

    def __str__(self) -> str:
        return f"Tenant(name={self.name!r}, tier={self.tier})"


# ---------------------------------------------------------------------------
# Key store
# ---------------------------------------------------------------------------


class TenantKeyStore:
    """In-memory key store loaded from environment variables.

    Thread-safe for reads after initialisation (keys are immutable
    after load).  Call ``reload()`` to hot-reload without restart.
    """

    _ENV_MULTI: ClassVar[str] = "SENTINAI_API_KEYS"
    _ENV_SINGLE: ClassVar[str] = "SENTINAI_API_KEY"

    def __init__(self) -> None:
        self._store: dict[str, Tenant] = {}
        self._load()

    def _load(self) -> None:
        raw_multi = os.getenv(self._ENV_MULTI, "")
        raw_single = os.getenv(self._ENV_SINGLE, "")

        if raw_multi:
            try:
                mapping: dict = json.loads(raw_multi)
            except json.JSONDecodeError as exc:
                logger.error(
                    "[Auth] %s contains invalid JSON — auth disabled: %s",
                    self._ENV_MULTI,
                    exc,
                )
                self._store = {}
                return

            store: dict[str, Tenant] = {}
            for key, config in mapping.items():
                if not isinstance(config, dict):
                    logger.warning("[Auth] Skipping malformed tenant config for key %r", key[:8])
                    continue
                name = config.get("name", "unknown")
                raw_tier = config.get("tier", "standard")
                try:
                    tier = RateLimitTier(raw_tier)
                except ValueError:
                    logger.warning(
                        "[Auth] Unknown tier %r for tenant %r — defaulting to standard",
                        raw_tier,
                        name,
                    )
                    tier = RateLimitTier.STANDARD
                store[key] = Tenant(
                    name=name,
                    tier=tier,
                    metadata=config.get("metadata", {}),
                )
            self._store = store
            logger.info("[Auth] Loaded %d tenant key(s) from %s", len(store), self._ENV_MULTI)

        elif raw_single:
            # Legacy single-key compatibility
            self._store = {raw_single: Tenant(name="default", tier=RateLimitTier.STANDARD)}
            logger.info(
                "[Auth] Loaded 1 tenant key from legacy %s (consider migrating to %s)",
                self._ENV_SINGLE,
                self._ENV_MULTI,
            )

        else:
            self._store = {}
            logger.warning(
                "[Auth] No API keys configured — running WITHOUT authentication. "
                "Set %s before any production deployment.",
                self._ENV_MULTI,
            )

    def reload(self) -> None:
        """Hot-reload keys from environment without restarting."""
        self._load()

    def lookup(self, key: str) -> Tenant | None:
        """Return the Tenant for *key*, or None if not found.

        Uses constant-time comparison to prevent timing attacks.
        """
        for stored_key, tenant in self._store.items():
            if secrets.compare_digest(key, stored_key):
                return tenant
        return None

    @property
    def auth_enabled(self) -> bool:
        return bool(self._store)

    @property
    def tenant_count(self) -> int:
        return len(self._store)


# Module-level singleton — loaded once at import time
_key_store = TenantKeyStore()


def get_key_store() -> TenantKeyStore:
    """FastAPI dependency that returns the shared key store."""
    return _key_store


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def require_tenant(
    key: str | None = Security(_api_key_header),
) -> Tenant:
    """FastAPI dependency — authenticates the request and returns the Tenant.

    Raises
    ------
    HTTP 401  key header is missing (when auth is enabled)
    HTTP 403  key is present but not recognised
    """
    if not _key_store.auth_enabled:
        # Dev/demo mode — return a synthetic tenant so downstream code
        # always has a Tenant object regardless of auth state
        return Tenant(name="anonymous", tier=RateLimitTier.INTERNAL)

    if key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    tenant = _key_store.lookup(key)
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )

    return tenant
