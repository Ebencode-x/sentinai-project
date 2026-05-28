"""Tests for provider factory."""

import pytest

from sentinai.llm.exceptions import LLMProviderError
from sentinai.llm.factory import build_provider
from sentinai.llm.mock import MockProvider


def test_build_mock_provider() -> None:
    p = build_provider("mock")
    assert isinstance(p, MockProvider)


def test_build_unknown_provider_raises() -> None:
    with pytest.raises(LLMProviderError, match="Unknown LLM provider"):
        build_provider("nonexistent")


def test_build_anthropic_without_key_returns_smart_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    from sentinai.llm.smart_stub import SmartStubProvider
    p = build_provider("anthropic")
    assert isinstance(p, SmartStubProvider)


def test_build_anthropic_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    from sentinai.llm.anthropic import AnthropicProvider

    p = build_provider("anthropic")
    assert isinstance(p, AnthropicProvider)


def test_env_var_selects_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTINAI_LLM_PROVIDER", "mock")
    p = build_provider()
    assert isinstance(p, MockProvider)
