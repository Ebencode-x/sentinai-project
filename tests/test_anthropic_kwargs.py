import asyncio
import inspect
from types import SimpleNamespace

from anthropic.resources.messages import AsyncMessages

from sentinai.llm.anthropic import AnthropicProvider
from sentinai.llm.base import LLMMessage, LLMRequest, Role


class _Usage:
    input_tokens = 1
    output_tokens = 1


class _Block:
    text = "ok"


class _Resp:
    content = [_Block()]
    model = "m"
    usage = _Usage()
    id = "r1"


class _FakeStream:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    @property
    def text_stream(self):
        async def gen():
            yield "a"

        return gen()


class _FakeMessages:
    def __init__(self):
        self.seen = {}

    async def create(self, **kwargs):
        self.seen["create"] = kwargs
        return _Resp()

    def stream(self, **kwargs):
        self.seen["stream"] = kwargs
        return _FakeStream()


def _request():
    return LLMRequest(
        messages=(
            LLMMessage(role=Role.SYSTEM, content="s"),
            LLMMessage(role=Role.USER, content="q"),
        ),
        model="claude-sonnet-4-6",
        max_tokens=100,
        temperature=0.2,
    )


def _run():
    fake = _FakeMessages()
    provider = AnthropicProvider("test-key")
    provider._client = SimpleNamespace(messages=fake)

    async def go():
        await provider.complete(_request())
        async for _ in provider.stream(_request()):
            pass

    asyncio.run(go())
    return fake.seen


def test_kwargs_match_real_sdk_signature():
    seen = _run()
    for name in ("create", "stream"):
        allowed = set(inspect.signature(getattr(AsyncMessages, name)).parameters)
        extra = set(seen[name]) - allowed
        assert not extra, f"{name} got kwargs the SDK does not accept: {extra}"


def test_temperature_not_sent_to_anthropic():
    seen = _run()
    assert "temperature" not in seen["create"]
    assert "temperature" not in seen["stream"]
