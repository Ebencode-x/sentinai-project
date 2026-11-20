import asyncio

import httpx
import pytest

from sentinai.llm.base import LLMMessage, LLMProvider, LLMRequest, LLMResponse, Role
from sentinai.llm.breaker import BreakerState, CircuitBreaker, get_breaker
from sentinai.llm.exceptions import LLMAuthError, LLMServerError
from sentinai.llm.factory import make_resilient
from sentinai.llm.mock import MockProvider
from sentinai.llm.openai_compat import OpenAICompatProvider
from sentinai.llm.resilient import ResilientProvider
from sentinai.llm.smart_stub import SmartStubProvider


class FailingProvider(LLMProvider):
    provider_name = "failing"

    def __init__(self, error):
        self.error = error
        self.calls = 0

    async def complete(self, request):
        self.calls += 1
        raise self.error

    async def stream(self, request):
        self.calls += 1
        raise self.error
        yield ""


class PartialProvider(LLMProvider):
    provider_name = "partial"

    async def complete(self, request):
        raise NotImplementedError

    async def stream(self, request):
        yield "partial "
        raise LLMServerError("connection cut")


class OkProvider(LLMProvider):
    provider_name = "ok"

    async def complete(self, request):
        return LLMResponse(
            content="live answer", model="m", provider="ok", input_tokens=1, output_tokens=2
        )

    async def stream(self, request):
        yield "live "
        yield "answer"


def _request(text="hello"):
    return LLMRequest(messages=(LLMMessage(Role.USER, text),), model="m")


def _wrap(primary, threshold=2):
    breaker = CircuitBreaker("t", threshold, 60.0)
    return ResilientProvider(primary, SmartStubProvider(), breaker, pace_seconds=0.0)


async def _collect(provider, request):
    return [chunk async for chunk in provider.stream(request)]


def test_complete_falls_back_with_an_honest_notice():
    resp = asyncio.run(_wrap(FailingProvider(LLMServerError("503"))).complete(_request()))
    assert resp.provider == "smart_stub"
    assert "Provider unavailable" in resp.content
    assert "ANTHROPIC_API_KEY" not in resp.content


def test_healthy_primary_is_untouched():
    provider = _wrap(OkProvider())
    resp = asyncio.run(provider.complete(_request()))
    assert resp.content == "live answer"
    assert provider.breaker.state is BreakerState.CLOSED


def test_open_circuit_skips_the_primary():
    primary = FailingProvider(LLMServerError("503"))
    provider = _wrap(primary, threshold=2)
    for _ in range(4):
        resp = asyncio.run(provider.complete(_request()))
        assert resp.provider == "smart_stub"
    assert primary.calls == 2
    assert provider.breaker.state is BreakerState.OPEN


def test_permanent_errors_are_not_masked_or_counted():
    provider = _wrap(FailingProvider(LLMAuthError("bad key")), threshold=1)
    with pytest.raises(LLMAuthError):
        asyncio.run(provider.complete(_request()))
    assert provider.breaker.state is BreakerState.CLOSED


def test_stream_falls_back_before_the_first_token():
    provider = _wrap(FailingProvider(LLMServerError("503")))
    text = "".join(asyncio.run(_collect(provider, _request())))
    assert "Provider unavailable" in text
    assert "ANTHROPIC_API_KEY" not in text


def test_stream_error_after_the_first_token_propagates():
    provider = _wrap(PartialProvider(), threshold=1)
    seen = []

    async def run():
        async for chunk in provider.stream(_request()):
            seen.append(chunk)

    with pytest.raises(LLMServerError):
        asyncio.run(run())
    assert seen == ["partial "]
    assert provider.breaker.state is BreakerState.OPEN


def test_stream_success_keeps_the_circuit_closed():
    provider = _wrap(OkProvider(), threshold=1)
    assert asyncio.run(_collect(provider, _request())) == ["live ", "answer"]
    assert provider.breaker.state is BreakerState.CLOSED


def test_stream_skips_the_primary_when_the_circuit_is_open():
    primary = FailingProvider(LLMServerError("503"))
    provider = _wrap(primary, threshold=1)
    asyncio.run(_collect(provider, _request()))
    asyncio.run(_collect(provider, _request()))
    assert primary.calls == 1


def test_make_resilient_wraps_openai_compat_and_shares_the_host_breaker():
    primary = OpenAICompatProvider(api_key="k", base_url="https://llm.test/v1")
    wrapped = make_resilient(primary)
    assert isinstance(wrapped, ResilientProvider)
    assert wrapped.primary is primary
    assert wrapped.breaker is get_breaker("https://llm.test/v1/chat/completions")
    assert wrapped.breaker is get_breaker("https://llm.test")


def test_make_resilient_leaves_offline_and_wrapped_providers_alone():
    for provider in (SmartStubProvider(), MockProvider()):
        assert make_resilient(provider) is provider
    wrapped = make_resilient(OpenAICompatProvider(api_key="k", base_url="https://llm.test/v1"))
    assert make_resilient(wrapped) is wrapped


def test_503_storm_through_the_real_provider_stops_hitting_the_network(monkeypatch):
    monkeypatch.delenv("SENTINAI_BREAKER_THRESHOLD", raising=False)
    monkeypatch.delenv("SENTINAI_BREAKER_COOLDOWN", raising=False)
    hits = []

    def handler(request):
        hits.append(request.url.host)
        return httpx.Response(503, text="busy")

    primary = OpenAICompatProvider(
        api_key="k", base_url="https://llm.test/v1", transport=httpx.MockTransport(handler)
    )
    provider = make_resilient(primary)
    for _ in range(6):
        resp = asyncio.run(provider.complete(_request()))
        assert resp.provider == "smart_stub"
    assert len(hits) == 3
