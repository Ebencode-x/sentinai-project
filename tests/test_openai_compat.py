import asyncio
import json

import httpx
import pytest

from sentinai.llm.base import LLMMessage, LLMRequest, Role
from sentinai.llm.exceptions import (
    LLMAuthError,
    LLMProviderError,
    LLMRateLimitError,
)
from sentinai.llm.factory import build_provider
from sentinai.llm.openai_compat import OpenAICompatProvider
from sentinai.llm.smart_stub import SmartStubProvider

_BASE = "https://example.test/v1beta/openai/"


def _req() -> LLMRequest:
    return LLMRequest(
        messages=(
            LLMMessage(role=Role.SYSTEM, content="sys"),
            LLMMessage(role=Role.USER, content="hi"),
        ),
        model="gemini-2.5-flash",
        max_tokens=50,
        temperature=0.2,
    )


def _provider(handler) -> OpenAICompatProvider:
    return OpenAICompatProvider("k-123", _BASE, transport=httpx.MockTransport(handler))


def test_complete_sends_openai_payload_and_parses_reply():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "r1",
                "model": "m",
                "choices": [{"message": {"content": "hello"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            },
        )

    resp = asyncio.run(_provider(handler).complete(_req()))
    assert seen["url"] == "https://example.test/v1beta/openai/chat/completions"
    assert seen["auth"] == "Bearer k-123"
    assert seen["body"]["model"] == "gemini-2.5-flash"
    assert seen["body"]["messages"][0] == {"role": "system", "content": "sys"}
    assert resp.content == "hello"
    assert resp.total_tokens == 5


def test_stream_yields_tokens_until_done():
    body = (
        b'data: {"choices":[{"delta":{"content":"he"}}]}\n\n'
        b'data: {"choices":[{"delta":{"content":"llo"}}]}\n\n'
        b'data: {"choices":[]}\n\n'
        b"data: [DONE]\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["stream"] is True
        return httpx.Response(200, content=body)

    async def collect() -> list[str]:
        return [t async for t in _provider(handler).stream(_req())]

    assert asyncio.run(collect()) == ["he", "llo"]


@pytest.mark.parametrize(
    ("status", "exc"),
    [
        (401, LLMAuthError),
        (403, LLMAuthError),
        (429, LLMRateLimitError),
        (400, LLMProviderError),
        (500, LLMProviderError),
    ],
)
def test_http_errors_are_mapped(status, exc):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text="boom")

    with pytest.raises(exc):
        asyncio.run(_provider(handler).complete(_req()))

    async def drain() -> None:
        async for _ in _provider(handler).stream(_req()):
            pass

    with pytest.raises(exc):
        asyncio.run(drain())


def test_plain_http_base_url_is_rejected():
    with pytest.raises(LLMProviderError):
        OpenAICompatProvider("k", "http://example.com/v1")


def test_factory_builds_openai_compat(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "k-123")
    monkeypatch.setenv("LLM_BASE_URL", _BASE)
    assert isinstance(build_provider("openai_compat"), OpenAICompatProvider)


def test_factory_without_key_falls_back_to_stub(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert isinstance(build_provider("openai_compat"), SmartStubProvider)


def test_factory_with_key_but_no_base_url_raises(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "k-123")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    with pytest.raises(LLMProviderError):
        build_provider("openai_compat")
