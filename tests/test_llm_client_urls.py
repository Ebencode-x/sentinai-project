"""Provider URLs live in named constants and the OpenAI URL is a constructor argument."""

import inspect

from src.integrations import llm_client
from src.integrations.llm_client import (
    ANTHROPIC_MESSAGES_URL,
    OPENAI_CHAT_URL,
    OpenAILLMClient,
)


def test_openai_client_defaults_to_openai_url() -> None:
    client = OpenAILLMClient(api_key="k", model="m", timeout_seconds=1.0)
    assert client.chat_url == OPENAI_CHAT_URL
    assert OPENAI_CHAT_URL == "https://api.openai.com/v1/chat/completions"


def test_openai_client_takes_chat_url_in_constructor() -> None:
    url = "https://example.test/v1/chat/completions"
    client = OpenAILLMClient(api_key="k", model="m", timeout_seconds=1.0, chat_url=url)
    assert client.chat_url == url


def test_provider_urls_are_written_once() -> None:
    source = inspect.getsource(llm_client)
    assert source.count("https://api.anthropic.com/v1/messages") == 1
    assert source.count("https://api.openai.com/v1/chat/completions") == 1
    assert ANTHROPIC_MESSAGES_URL == "https://api.anthropic.com/v1/messages"
