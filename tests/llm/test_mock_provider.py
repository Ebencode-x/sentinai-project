"""Tests for MockProvider — zero network."""

import pytest

from sentinai.llm.base import LLMMessage, LLMRequest, Role
from sentinai.llm.exceptions import LLMProviderError
from sentinai.llm.mock import MockProvider


def _req(text: str = "ping") -> LLMRequest:
    return LLMRequest(
        messages=(LLMMessage(role=Role.USER, content=text),),
        model="mock-model",
    )


@pytest.mark.asyncio
async def test_complete_returns_response() -> None:
    p = MockProvider(response="pong")
    resp = await p.complete(_req())
    assert resp.content == "pong"
    assert resp.provider == "mock"
    assert len(p.calls) == 1


@pytest.mark.asyncio
async def test_complete_records_calls() -> None:
    p = MockProvider()
    await p.complete(_req("a"))
    await p.complete(_req("b"))
    assert len(p.calls) == 2


@pytest.mark.asyncio
async def test_complete_raises_on_demand() -> None:
    p = MockProvider(raise_on_complete=LLMProviderError("boom"))
    with pytest.raises(LLMProviderError, match="boom"):
        await p.complete(_req())


@pytest.mark.asyncio
async def test_stream_yields_tokens() -> None:
    p = MockProvider(response="hello world")
    tokens = [t async for t in p.stream(_req())]
    assert "".join(tokens).strip() == "hello world"


@pytest.mark.asyncio
async def test_stream_raises_on_demand() -> None:
    p = MockProvider(raise_on_stream=LLMProviderError("stream-fail"))
    with pytest.raises(LLMProviderError):
        async for _ in p.stream(_req()):
            pass
