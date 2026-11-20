import asyncio

import httpx
import pytest

from sentinai.llm import breaker as br
from sentinai.llm.exceptions import (
    LLMAuthError,
    LLMCircuitOpenError,
    LLMProviderError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
)


@pytest.fixture(autouse=True)
def _fresh_registry():
    br.reset_breakers()
    yield
    br.reset_breakers()


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def make(threshold=3, cooldown=60.0):
    clock = Clock()
    return br.CircuitBreaker("test", threshold, cooldown, clock=clock), clock


def fail(b):
    b.before_call()
    b.record_failure()


def test_opens_after_threshold_consecutive_failures():
    b, _ = make()
    fail(b)
    fail(b)
    assert b.state is br.BreakerState.CLOSED
    fail(b)
    assert b.state is br.BreakerState.OPEN
    with pytest.raises(LLMCircuitOpenError):
        b.before_call()


def test_success_resets_the_failure_count():
    b, _ = make()
    fail(b)
    fail(b)
    b.before_call()
    b.record_success()
    fail(b)
    fail(b)
    assert b.state is br.BreakerState.CLOSED


def test_half_open_allows_a_single_probe_after_cooldown():
    b, clock = make(threshold=1)
    fail(b)
    clock.now += 59
    with pytest.raises(LLMCircuitOpenError):
        b.before_call()
    clock.now += 2
    b.before_call()
    assert b.state is br.BreakerState.HALF_OPEN
    with pytest.raises(LLMCircuitOpenError):
        b.before_call()


def test_probe_success_closes_the_circuit():
    b, clock = make(threshold=1)
    fail(b)
    clock.now += 61
    b.before_call()
    b.record_success()
    assert b.state is br.BreakerState.CLOSED
    b.before_call()


def test_probe_failure_reopens_with_a_fresh_cooldown():
    b, clock = make(threshold=1)
    fail(b)
    clock.now += 61
    b.before_call()
    b.record_failure()
    assert b.state is br.BreakerState.OPEN
    clock.now += 30
    with pytest.raises(LLMCircuitOpenError):
        b.before_call()


def test_abort_releases_the_probe_slot():
    b, clock = make(threshold=1)
    fail(b)
    clock.now += 61
    b.before_call()
    b.abort()
    b.before_call()


def test_probe_lease_expires_if_the_probe_never_reports():
    b, clock = make(threshold=1)
    fail(b)
    clock.now += 61
    b.before_call()
    clock.now += 61
    b.before_call()


def test_call_counts_transient_errors_but_not_permanent_ones():
    b, _ = make(threshold=2)

    def auth():
        raise LLMAuthError("bad key")

    def down():
        raise LLMServerError("503")

    for _ in range(5):
        with pytest.raises(LLMAuthError):
            b.call(auth)
    assert b.state is br.BreakerState.CLOSED
    for _ in range(2):
        with pytest.raises(LLMServerError):
            b.call(down)
    assert b.state is br.BreakerState.OPEN
    with pytest.raises(LLMCircuitOpenError):
        b.call(lambda: "never")


def test_acall_trips_and_cancellation_releases_the_probe():
    b, clock = make(threshold=1)

    async def down():
        raise LLMServerError("503")

    async def cancelled():
        raise asyncio.CancelledError()

    async def ok():
        return "ok"

    async def scenario():
        with pytest.raises(LLMServerError):
            await b.acall(down)
        assert b.state is br.BreakerState.OPEN
        clock.now += 61
        with pytest.raises(asyncio.CancelledError):
            await b.acall(cancelled)
        assert await b.acall(ok) == "ok"

    asyncio.run(scenario())
    assert b.state is br.BreakerState.CLOSED


def _status_error(code):
    req = httpx.Request("POST", "https://x.test")
    return httpx.HTTPStatusError("x", request=req, response=httpx.Response(code, request=req))


@pytest.mark.parametrize(
    "exc, expected",
    [
        (LLMRateLimitError("x"), True),
        (LLMTimeoutError("x"), True),
        (LLMServerError("x"), True),
        (LLMAuthError("x"), False),
        (LLMProviderError("x"), False),
        (LLMCircuitOpenError("x"), False),
        (httpx.ConnectError("x"), True),
        (httpx.ReadTimeout("x"), True),
        (httpx.UnsupportedProtocol("x"), False),
        (_status_error(503), True),
        (_status_error(429), True),
        (_status_error(400), False),
        (_status_error(401), False),
        (ValueError("x"), False),
    ],
)
def test_is_transient(exc, expected):
    assert br.is_transient(exc) is expected


def test_registry_shares_one_breaker_per_host():
    a = br.get_breaker("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions")
    b = br.get_breaker("https://generativelanguage.googleapis.com/v1beta/openai")
    c = br.get_breaker("https://api.openai.com/v1/chat/completions")
    assert a is b
    assert a is not c


def test_env_overrides_and_bad_values_fall_back(monkeypatch):
    monkeypatch.setenv("SENTINAI_BREAKER_THRESHOLD", "5")
    monkeypatch.setenv("SENTINAI_BREAKER_COOLDOWN", "abc")
    snap = br.get_breaker("h.test").snapshot()
    assert snap["threshold"] == 5
    assert snap["cooldown_seconds"] == 60.0
    monkeypatch.setenv("SENTINAI_BREAKER_THRESHOLD", "0")
    assert br.get_breaker("other.test").snapshot()["threshold"] == 3
