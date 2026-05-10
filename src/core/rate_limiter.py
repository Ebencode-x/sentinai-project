"""Token-bucket rate limiter for LLM calls and GitHub PR creation.

Prevents log storms from generating hundreds of LLM calls or PRs.
Configurable via environment variables.

Architecture:
    RateLimiter (Protocol) — interface contract
    TokenBucket            — in-memory implementation (current)
    Future: RedisRateLimiter — distributed implementation (Phase 3)
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)

_LLM_MAX_PER_MINUTE: int = int(os.getenv("SENTINAI_LLM_RATE_LIMIT", "10"))
_PR_MAX_PER_MINUTE: int = int(os.getenv("SENTINAI_PR_RATE_LIMIT", "3"))


@runtime_checkable
class RateLimiter(Protocol):
    """Interface contract for all rate limiter implementations.

    Any class that implements consume() satisfies this protocol.
    Swap TokenBucket for RedisRateLimiter in production without
    changing any call sites.
    """

    def consume(self) -> bool:
        """Attempt to consume one token.

        Returns:
            True  — request is allowed.
            False — request is throttled; caller should reject or defer.
        """
        ...


class TokenBucket:
    """Thread-safe token bucket rate limiter.

    Refills at a constant rate. Callers consume one token per action.
    Returns False immediately (non-blocking) when the bucket is empty.

    Satisfies the RateLimiter protocol.
    """

    def __init__(self, capacity: int, refill_per_minute: int) -> None:
        self._capacity = capacity
        self._tokens = float(capacity)
        self._refill_rate = refill_per_minute / 60.0
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def consume(self) -> bool:
        """Attempt to consume one token. Returns True if allowed, False if throttled."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(
                self._capacity,
                self._tokens + elapsed * self._refill_rate,
            )
            self._last_refill = now

            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True

            return False


# Global instances — both satisfy RateLimiter protocol.
# Type annotations use RateLimiter so future swap requires zero call-site changes.
llm_rate_limiter: RateLimiter = TokenBucket(
    capacity=_LLM_MAX_PER_MINUTE,
    refill_per_minute=_LLM_MAX_PER_MINUTE,
)

pr_rate_limiter: RateLimiter = TokenBucket(
    capacity=_PR_MAX_PER_MINUTE,
    refill_per_minute=_PR_MAX_PER_MINUTE,
)
