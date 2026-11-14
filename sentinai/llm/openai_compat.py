"""OpenAI-compatible provider (Gemini, Groq, OpenRouter and others) over httpx."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator

import httpx

from sentinai.llm.base import LLMProvider, LLMRequest, LLMResponse
from sentinai.llm.exceptions import (
    LLMAuthError,
    LLMError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)

_TIMEOUT = float(os.getenv("SENTINAI_LLM_TIMEOUT", "30"))
_MAX_ERROR_CHARS = 300
_SAFE_PREFIXES = ("https://", "http://localhost:", "http://127.0.0.1:")


def _payload(request: LLMRequest, stream: bool) -> dict:
    return {
        "model": request.model,
        "messages": [{"role": m.role.value, "content": m.content} for m in request.messages],
        "max_tokens": request.max_tokens,
        "temperature": request.temperature,
        "stream": stream,
    }


def _status_error(status: int, text: str) -> LLMError:
    detail = " ".join(text.split())[:_MAX_ERROR_CHARS]
    message = f"HTTP {status}: {detail}"
    if status in (401, 403):
        return LLMAuthError(message)
    if status == 429:
        return LLMRateLimitError(message)
    return LLMProviderError(message)


def _delta_text(data: str) -> str:
    try:
        chunk = json.loads(data)
        choices = chunk.get("choices") or []
        if not choices:
            return ""
        return choices[0].get("delta", {}).get("content") or ""
    except (ValueError, AttributeError, TypeError):
        return ""


class OpenAICompatProvider(LLMProvider):
    provider_name = "openai_compat"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise LLMAuthError("LLM API key must not be empty.")
        base_url = (base_url or "").strip().rstrip("/")
        if not base_url.startswith(_SAFE_PREFIXES):
            raise LLMProviderError("LLM_BASE_URL must be set and start with https://.")
        self._url = base_url + "/chat/completions"
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=_TIMEOUT, transport=self._transport)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        t0 = self._now_ms()
        try:
            async with self._client() as client:
                resp = await client.post(
                    self._url, headers=self._headers, json=_payload(request, False)
                )
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("Request timed out.") from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"Network error: {type(exc).__name__}") from exc
        if resp.status_code >= 400:
            raise _status_error(resp.status_code, resp.text)
        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"] or ""
            usage = data.get("usage") or {}
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError("Unexpected response schema.") from exc
        return LLMResponse(
            content=content,
            model=str(data.get("model", request.model)),
            provider=self.provider_name,
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
            latency_ms=self._now_ms() - t0,
            request_id=str(data.get("id", "")),
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        try:
            async with self._client() as client:
                async with client.stream(
                    "POST", self._url, headers=self._headers, json=_payload(request, True)
                ) as resp:
                    if resp.status_code >= 400:
                        body = (await resp.aread()).decode("utf-8", "replace")
                        raise _status_error(resp.status_code, body)
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        delta = _delta_text(data)
                        if delta:
                            yield delta
        except LLMError:
            raise
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("Request timed out.") from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"Network error: {type(exc).__name__}") from exc
