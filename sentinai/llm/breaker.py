"""Circuit breaker shared by every LLM call path.

One breaker per provider host lives in a process-wide registry, so the sync
remediation stack (src/integrations/llm_client.py) and the async chat stack
(sentinai/llm) trip and recover together when the same provider goes down.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import TypedDict, TypeVar
from urllib.parse import urlparse

import httpx

from sentinai.llm.exceptions import TRANSIENT_ERRORS, LLMCircuitOpenError

logger = logging.getLogger(__name__)

T = TypeVar("T")

DEFAULT_THRESHOLD = 3
DEFAULT_COOLDOWN_SECONDS = 60.0


class BreakerState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


def is_transient(exc: BaseException) -> bool:
    """True when the failure says the provider is unavailable, not that we are misconfigured."""
    if isinstance(exc, TRANSIENT_ERRORS):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code == 429 or code >= 500
    if isinstance(exc, httpx.UnsupportedProtocol):
        return False
    return isinstance(exc, httpx.TransportError)


class BreakerSnapshot(TypedDict):
    name: str
    state: str
    failures: int
    threshold: int
    cooldown_seconds: float
    retry_in_seconds: float


class CircuitBreaker:
    """Consecutive transient failures open the circuit; one probe tests recovery."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = DEFAULT_THRESHOLD,
        cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1.")
        if cooldown_seconds <= 0:
            raise ValueError("cooldown_seconds must be > 0.")
        self.name = name
        self._threshold = failure_threshold
        self._cooldown = cooldown_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._state = BreakerState.CLOSED
        self._failures = 0
        self._opened_at = 0.0
        self._probe_started: float | None = None

    @property
    def state(self) -> BreakerState:
        with self._lock:
            return self._state

    def before_call(self) -> None:
        """Raise LLMCircuitOpenError unless a call may go through right now."""
        with self._lock:
            now = self._clock()
            if self._state is BreakerState.CLOSED:
                return
            if self._state is BreakerState.OPEN:
                wait = self._opened_at + self._cooldown - now
                if wait > 0:
                    raise LLMCircuitOpenError(
                        f"Circuit open for {self.name}: retry in {wait:.0f}s."
                    )
                self._state = BreakerState.HALF_OPEN
                self._probe_started = now
                logger.info("Circuit %s half-open: sending one probe.", self.name)
                return
            started = self._probe_started
            if started is not None and now - started < self._cooldown:
                raise LLMCircuitOpenError(f"Circuit open for {self.name}: probe in progress.")
            self._probe_started = now

    def record_success(self) -> None:
        with self._lock:
            if self._state is not BreakerState.CLOSED:
                logger.info("Circuit %s closed again.", self.name)
            self._state = BreakerState.CLOSED
            self._failures = 0
            self._probe_started = None

    def record_failure(self) -> None:
        with self._lock:
            now = self._clock()
            if self._state is BreakerState.HALF_OPEN:
                self._trip(now)
                return
            self._failures += 1
            if self._state is BreakerState.CLOSED and self._failures >= self._threshold:
                self._trip(now)

    def abort(self) -> None:
        """The call ended without proving anything (permanent error or cancellation)."""
        with self._lock:
            if self._state is BreakerState.HALF_OPEN:
                self._probe_started = None

    def _trip(self, now: float) -> None:
        self._state = BreakerState.OPEN
        self._opened_at = now
        self._probe_started = None
        logger.warning(
            "Circuit %s opened for %.0fs after %d transient failure(s).",
            self.name,
            self._cooldown,
            self._failures,
        )

    def _settle(self, exc: BaseException) -> None:
        if is_transient(exc):
            self.record_failure()
        else:
            self.abort()

    def call(self, fn: Callable[[], T]) -> T:
        self.before_call()
        try:
            result = fn()
        except BaseException as exc:
            self._settle(exc)
            raise
        self.record_success()
        return result

    async def acall(self, fn: Callable[[], Awaitable[T]]) -> T:
        self.before_call()
        try:
            result = await fn()
        except BaseException as exc:
            self._settle(exc)
            raise
        self.record_success()
        return result

    def snapshot(self) -> BreakerSnapshot:
        with self._lock:
            retry_in = 0.0
            if self._state is BreakerState.OPEN:
                retry_in = max(0.0, self._opened_at + self._cooldown - self._clock())
            return {
                "name": self.name,
                "state": self._state.value,
                "failures": self._failures,
                "threshold": self._threshold,
                "cooldown_seconds": self._cooldown,
                "retry_in_seconds": round(retry_in, 1),
            }


_REGISTRY: dict[str, CircuitBreaker] = {}
_REGISTRY_LOCK = threading.Lock()


def _env_number(name: str, default: float, cast: Callable[[str], float]) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = cast(raw)
    except ValueError:
        value = 0
    if value <= 0:
        logger.warning("Ignoring invalid %s=%r, using %s.", name, raw, default)
        return default
    return value


def breaker_key(url_or_host: str) -> str:
    text = (url_or_host or "").strip().lower()
    return urlparse(text).hostname or text


def get_breaker(url_or_host: str) -> CircuitBreaker:
    """Return the shared breaker for a provider URL or host, creating it on first use."""
    key = breaker_key(url_or_host)
    with _REGISTRY_LOCK:
        breaker = _REGISTRY.get(key)
        if breaker is None:
            breaker = CircuitBreaker(
                key,
                int(_env_number("SENTINAI_BREAKER_THRESHOLD", DEFAULT_THRESHOLD, int)),
                _env_number("SENTINAI_BREAKER_COOLDOWN", DEFAULT_COOLDOWN_SECONDS, float),
            )
            _REGISTRY[key] = breaker
        return breaker


def breaker_snapshots() -> list[BreakerSnapshot]:
    with _REGISTRY_LOCK:
        breakers = list(_REGISTRY.values())
    return [b.snapshot() for b in breakers]


def reset_breakers() -> None:
    with _REGISTRY_LOCK:
        _REGISTRY.clear()
