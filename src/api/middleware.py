"""Phase 2 — Per-tenant rate limiting middleware.

Each authenticated tenant gets an isolated TokenBucket sized to their
tier limit.  Buckets are created lazily on first request and live for
the process lifetime (resets on restart — acceptable for MVP).

Tier limits (requests / minute)
--------------------------------
standard   60
premium   300
internal  unlimited

HTTP responses
--------------
429 Too Many Requests   tenant bucket exhausted
    Retry-After header  seconds until next token available (approx)
"""

from __future__ import annotations

import logging
import threading

from fastapi import HTTPException, status

from src.api.auth import TIER_LIMITS, Tenant
from src.core.rate_limiter import TokenBucket

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-tenant bucket registry
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_buckets: dict[str, TokenBucket] = {}


def _get_bucket(tenant: Tenant) -> TokenBucket | None:
    """Return (or lazily create) the TokenBucket for *tenant*.

    Returns None when the tenant tier is unlimited (INTERNAL).
    """
    limit = TIER_LIMITS.get(tenant.tier)
    if limit is None:
        return None  # unlimited

    with _lock:
        if tenant.name not in _buckets:
            _buckets[tenant.name] = TokenBucket(
                capacity=limit,
                refill_per_minute=limit,
            )
            logger.debug(
                "[RateLimit] Created bucket for tenant=%r tier=%s limit=%d/min",
                tenant.name,
                tenant.tier,
                limit,
            )
        return _buckets[tenant.name]


def reset_bucket(tenant_name: str) -> None:
    """Remove the bucket for *tenant_name* (used in tests)."""
    with _lock:
        _buckets.pop(tenant_name, None)


def reset_all_buckets() -> None:
    """Clear all tenant buckets (used in tests)."""
    with _lock:
        _buckets.clear()


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


def enforce_rate_limit(tenant: Tenant) -> None:
    """Check the tenant's rate-limit bucket and raise 429 if exhausted.

    Designed to be called from a FastAPI dependency or route handler
    after ``require_tenant`` has resolved the Tenant.

    Parameters
    ----------
    tenant:
        The authenticated tenant (resolved by ``require_tenant``).
    """
    bucket = _get_bucket(tenant)
    if bucket is None:
        # Internal / unlimited tier — always allow
        return

    if not bucket.consume():
        limit = TIER_LIMITS[tenant.tier]
        retry_after = max(1, int(60 / limit)) if limit else 1
        logger.warning(
            "[RateLimit] Tenant %r exhausted rate limit (tier=%s, %d req/min)",
            tenant.name,
            tenant.tier,
            limit or 0,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Rate limit exceeded for tier '{tenant.tier}'. Limit: {limit} requests/minute."
            ),
            headers={"Retry-After": str(retry_after)},
        )
