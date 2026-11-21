import asyncio

import anthropic
import httpx
import pytest

from sentinai.llm.anthropic import _map_error
from sentinai.llm.base import LLMMessage, LLMRequest, Role
from sentinai.llm.exceptions import (
    LLMAuthError,
    LLMError,
    LLMProviderError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
)
from sentinai.llm.openai_compat import OpenAICompatProvider

URL = "https://llm.test/v1"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


def _provider(handler):
    return OpenAICompatProvider(api_key="k", base_url=URL, transport=httpx.MockTransport(handler))


def _request():
    return LLMRequest(messages=(LLMMessage(Role.USER, "hi"),), model="m")


async def _drain(provider):
    async for _ in provider.stream(_request()):
        pass


@pytest.mark.parametrize(
    "status, expected",
    [
        (503, LLMServerError),
        (500, LLMServerError),
        (429, LLMRateLimitError),
        (401, LLMAuthError),
        (400, LLMProviderError),
    ],
)
def test_openai_compat_status_classes(status, expected):
    provider = _provider(lambda request: httpx.Response(status, text="nope"))
    with pytest.raises(LLMError) as info:
        asyncio.run(provider.complete(_request()))
    assert type(info.value) is expected


def test_openai_compat_stream_503_is_a_server_error():
    provider = _provider(lambda request: httpx.Response(503, text="busy"))
    with pytest.raises(LLMServerError):
        asyncio.run(_drain(provider))


def test_openai_compat_network_error_is_a_server_error():
    def handler(request):
        raise httpx.ConnectError("down", request=request)

    with pytest.raises(LLMServerError):
        asyncio.run(_provider(handler).complete(_request()))


def _http(status):
    return httpx.Response(status, request=httpx.Request("POST", ANTHROPIC_URL))


def test_anthropic_error_mapping():
    req = httpx.Request("POST", ANTHROPIC_URL)
    boom = anthropic.InternalServerError("boom", response=_http(529), body=None)
    assert type(_map_error(boom)) is LLMServerError
    assert type(_map_error(anthropic.APIConnectionError(request=req))) is LLMServerError
    assert type(_map_error(anthropic.APITimeoutError(request=req))) is LLMTimeoutError
    credit = anthropic.BadRequestError("credit", response=_http(400), body=None)
    assert type(_map_error(credit)) is LLMProviderError
