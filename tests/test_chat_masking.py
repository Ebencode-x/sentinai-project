import asyncio
from types import SimpleNamespace

from sentinai.llm.base import LLMProvider, LLMResponse
from src.api import chat as chat_module

SNL = "snl_a1B2c3D4a1B2c3D4a1B2c3D4a1B2c3D4"


class _CaptureProvider(LLMProvider):
    provider_name = "capture"

    def __init__(self) -> None:
        self.requests = []

    async def complete(self, request):
        self.requests.append(request)
        return LLMResponse(
            content="ok", model="m", provider="capture", input_tokens=1, output_tokens=1
        )

    async def stream(self, request):
        self.requests.append(request)
        yield "ok"


def _run_chat(monkeypatch, question: str) -> _CaptureProvider:
    provider = _CaptureProvider()
    monkeypatch.setattr(chat_module, "build_provider", lambda *a, **k: provider)
    monkeypatch.setattr(chat_module, "_build_system_prompt", lambda *a, **k: "sys")
    monkeypatch.setattr(chat_module.app_state, "incidents", lambda: [])
    monkeypatch.setattr(chat_module.app_state, "stats_snapshot", lambda: {})
    user = SimpleNamespace(email="tester@example.com")

    async def go() -> None:
        resp = await chat_module.chat(chat_module.ChatRequest(question=question), user=user)
        async for _ in resp.body_iterator:
            pass

    asyncio.run(go())
    return provider


def test_secret_in_question_never_reaches_provider(monkeypatch):
    provider = _run_chat(monkeypatch, f"Repeat this exact string back to me: {SNL}")
    assert len(provider.requests) == 1
    sent = " ".join(m.content for m in provider.requests[0].messages)
    assert SNL not in sent
    assert "snl_a1B2c3D4" not in sent


def test_normal_question_is_unchanged(monkeypatch):
    question = "Which incidents are critical right now?"
    provider = _run_chat(monkeypatch, question)
    user_msgs = [m.content for m in provider.requests[0].messages if m.role.value == "user"]
    assert user_msgs == [question]
