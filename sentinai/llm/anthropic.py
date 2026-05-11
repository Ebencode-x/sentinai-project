"""Anthropic (Claude) provider implementation."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

try:
    import anthropic
    from anthropic import AsyncAnthropic
except ImportError as e:
    raise ImportError("Install the Anthropic SDK: pip install anthropic") from e

from sentinai.llm.base import LLMProvider, LLMRequest, LLMResponse, Role
from sentinai.llm.exceptions import (
    LLMAuthError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)

_TIMEOUT = float(os.getenv("SENTINAI_LLM_TIMEOUT", "30"))


def _build_messages(request: LLMRequest) -> tuple[str | None, list[dict]]:
    system: str | None = None
    messages: list[dict] = []
    for msg in request.messages:
        if msg.role is Role.SYSTEM:
            system = msg.content
        else:
            messages.append({"role": msg.role.value, "content": msg.content})
    return system, messages


def _map_error(exc: Exception) -> LLMProviderError:
    if isinstance(exc, anthropic.AuthenticationError):
        return LLMAuthError(str(exc))
    if isinstance(exc, anthropic.RateLimitError):
        return LLMRateLimitError(str(exc))
    if isinstance(exc, anthropic.APITimeoutError):
        return LLMTimeoutError(str(exc))
    return LLMProviderError(str(exc))


class AnthropicProvider(LLMProvider):
    provider_name = "anthropic"

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise LLMAuthError("Anthropic API key must not be empty.")
        self._client = AsyncAnthropic(api_key=api_key, timeout=_TIMEOUT)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        system, messages = _build_messages(request)
        t0 = self._now_ms()
        try:
            kwargs: dict = dict(
                model=request.model,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                messages=messages,
            )
            if system:
                kwargs["system"] = system
            resp = await self._client.messages.create(**kwargs)
        except Exception as exc:
            raise _map_error(exc) from exc

        return LLMResponse(
            content=resp.content[0].text,
            model=resp.model,
            provider=self.provider_name,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            latency_ms=self._now_ms() - t0,
            request_id=resp.id,
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        system, messages = _build_messages(request)
        try:
            kwargs: dict = dict(
                model=request.model,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                messages=messages,
            )
            if system:
                kwargs["system"] = system
            async with self._client.messages.stream(**kwargs) as s:
                async for chunk in s.text_stream:
                    yield chunk
        except Exception as exc:
            raise _map_error(exc) from exc
