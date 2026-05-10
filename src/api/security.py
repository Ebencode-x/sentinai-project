"""API key authentication dependency for SentinAI routes.

Usage:
    from src.api.security import require_api_key
    @router.get("/protected", dependencies=[Depends(require_api_key)])

Set SENTINAI_API_KEY in your .env to enable protection.
If the env var is not set, auth is disabled (dev/demo mode only).
"""

from __future__ import annotations

import logging
import os
import secrets

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

_API_KEY_NAME = "X-API-Key"
_api_key_header = APIKeyHeader(name=_API_KEY_NAME, auto_error=False)


def _get_configured_key() -> str:
    """Read API key dynamically — picks up changes without server restart."""
    return os.getenv("SENTINAI_API_KEY", "")


async def require_api_key(key: str | None = Security(_api_key_header)) -> None:
    """FastAPI dependency that enforces API key auth when SENTINAI_API_KEY is set.

    Skips auth when the key is not configured (local/demo mode).
    Returns 401 when key is missing, 403 when key is wrong.
    """
    configured_key = _get_configured_key()

    if not configured_key:
        logger.warning(
            "SENTINAI_API_KEY is not set — API is running without authentication. "
            "Set this variable before any public or production deployment."
        )
        return

    if key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if not secrets.compare_digest(key, configured_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )
