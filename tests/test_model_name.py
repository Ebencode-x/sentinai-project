from types import SimpleNamespace

from src.core.rate_limiter import llm_rate_limiter
from src.integrations.llm_client import (
    BaseLLMClient,
    ClaudeLLMClient,
    OpenAILLMClient,
    StubLLMClient,
)
from src.models.events import RemediationSuggestion
from src.services.remediation_engine import RemediationEngine


class FakeClient(BaseLLMClient):
    model_name = "fake-model-1"

    def analyze_incident(self, incident):
        return StubLLMClient().analyze_incident(incident)


class BoomClient(BaseLLMClient):
    model_name = "boom-model"

    def analyze_incident(self, incident):
        raise RuntimeError("provider down")


def _incident():
    return SimpleNamespace(incident_id="inc-test", trigger_line="boom")


def test_suggestion_model_defaults_to_none():
    s = RemediationSuggestion(
        summary="s",
        proposed_code_fix="c",
        proposed_config_change="k",
        confidence=0.5,
        risks="r",
    )
    assert s.model is None


def test_stub_model_name():
    assert StubLLMClient().model_name == "stub"


def test_openai_model_name_default_and_explicit():
    assert OpenAILLMClient("k", "", 1.0).model_name == "gpt-4o-mini"
    assert OpenAILLMClient("k", "gpt-4o", 1.0).model_name == "gpt-4o"


def test_claude_model_name_default_and_explicit():
    assert ClaudeLLMClient("k", "", 1.0).model_name == "claude-sonnet-4-20250514"
    assert ClaudeLLMClient("k", "claude-x", 1.0).model_name == "claude-x"


def test_engine_stamps_client_model_on_success(monkeypatch):
    monkeypatch.setattr(llm_rate_limiter, "consume", lambda: True)
    engine = RemediationEngine(llm_client=FakeClient())
    result = engine.suggest_fix(_incident())
    assert result.model == "fake-model-1"
    assert result.source == "stub"


def test_engine_stamps_stub_on_provider_failure(monkeypatch):
    monkeypatch.setattr(llm_rate_limiter, "consume", lambda: True)
    engine = RemediationEngine(llm_client=BoomClient())
    result = engine.suggest_fix(_incident())
    assert result.source == "fallback"
    assert result.model == "stub"


def test_engine_stamps_stub_on_rate_limit(monkeypatch):
    monkeypatch.setattr(llm_rate_limiter, "consume", lambda: False)
    engine = RemediationEngine(llm_client=FakeClient())
    result = engine.suggest_fix(_incident())
    assert result.source == "fallback"
    assert result.model == "stub"
