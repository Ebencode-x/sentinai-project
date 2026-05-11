"""Tests for LLM base types."""

import pytest

from sentinai.llm.base import LLMMessage, LLMRequest, LLMResponse, Role


def test_llm_message_valid() -> None:
    msg = LLMMessage(role=Role.USER, content="hello")
    assert msg.content == "hello"


def test_llm_message_empty_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        LLMMessage(role=Role.USER, content="   ")


def test_llm_request_no_messages_raises() -> None:
    with pytest.raises(ValueError, match="at least one"):
        LLMRequest(messages=(), model="claude-3-5-sonnet-20241022")


def test_llm_request_bad_temperature_raises() -> None:
    msg = LLMMessage(role=Role.USER, content="hi")
    with pytest.raises(ValueError, match="temperature"):
        LLMRequest(messages=(msg,), model="m", temperature=3.0)


def test_llm_response_total_tokens() -> None:
    r = LLMResponse(
        content="ok",
        model="m",
        provider="mock",
        input_tokens=10,
        output_tokens=5,
    )
    assert r.total_tokens == 15
