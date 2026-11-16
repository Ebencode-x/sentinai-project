from dataclasses import replace

from src.core import env_check
from src.core.config import settings
from src.integrations import llm_client as lc

GEMINI = "https://generativelanguage.googleapis.com/v1beta/openai"


def _set(monkeypatch, **kw):
    for k, v in kw.items():
        monkeypatch.setattr(settings, k, v)


def test_openai_compat_uses_base_url_and_model(monkeypatch):
    _set(
        monkeypatch,
        llm_provider="openai_compat",
        llm_api_key="k",
        llm_base_url=GEMINI + "/",
        llm_model="gemini-3.5-flash-lite",
    )
    client = lc.build_llm_client()
    assert isinstance(client, lc.OpenAILLMClient)
    assert client.chat_url == GEMINI + "/chat/completions"
    assert client.model_name == "gemini-3.5-flash-lite"


def test_openai_compat_rejects_non_https(monkeypatch):
    _set(
        monkeypatch,
        llm_provider="openai_compat",
        llm_api_key="k",
        llm_base_url="http://evil.test/v1",
        llm_model="m",
    )
    assert isinstance(lc.build_llm_client(), lc.StubLLMClient)


def test_openai_compat_needs_model(monkeypatch):
    _set(
        monkeypatch,
        llm_provider="openai_compat",
        llm_api_key="k",
        llm_base_url=GEMINI,
        llm_model="",
    )
    assert isinstance(lc.build_llm_client(), lc.StubLLMClient)


def test_plain_openai_keeps_default_url(monkeypatch):
    _set(monkeypatch, llm_provider="openai", llm_api_key="k", llm_model="")
    client = lc.build_llm_client()
    assert client.chat_url == "https://api.openai.com/v1/chat/completions"


def test_env_check_flags_missing_base_url():
    cfg = replace(
        settings, llm_provider="openai_compat", llm_api_key="k", llm_base_url="", llm_model="m"
    )
    assert any("LLM_BASE_URL" in e for e in env_check.check_env(cfg).errors)
