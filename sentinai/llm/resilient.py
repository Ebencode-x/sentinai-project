"""Provider wrapper: shared circuit breaker plus offline fallback.

Transient failures (rate limit, timeout, 5xx, network) are counted by the
breaker and answered by the fallback provider, so chat keeps working while the
real provider is down. Permanent errors such as a bad API key are never masked.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import AsyncIterator

from sentinai.llm.base import LLMProvider, LLMRequest, LLMResponse
from sentinai.llm.breaker import CircuitBreaker
from sentinai.llm.exceptions import TRANSIENT_ERRORS, LLMCircuitOpenError
from sentinai.llm.smart_stub import _DEMO_NOTICE

logger = logging.getLogger(__name__)

FALLBACK_NOTICE = (
    "\n\n[Provider unavailable: this is an offline answer. "
    "Live AI answers resume automatically when the provider recovers.]"
)
_FALLBACK_ON = (*TRANSIENT_ERRORS, LLMCircuitOpenError)
_TOKEN = re.compile(r"\S+\s*|\s+")


class ResilientProvider(LLMProvider):
    provider_name = "resilient"

    def __init__(
        self,
        primary: LLMProvider,
        fallback: LLMProvider,
        breaker: CircuitBreaker,
        *,
        notice: str = FALLBACK_NOTICE,
        pace_seconds: float = 0.02,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._breaker = breaker
        self._notice = notice
        self._pace = pace_seconds

    @property
    def primary(self) -> LLMProvider:
        return self._primary

    @property
    def breaker(self) -> CircuitBreaker:
        return self._breaker

    def supports_streaming(self) -> bool:
        return self._primary.supports_streaming()

    async def complete(self, request: LLMRequest) -> LLMResponse:
        try:
            return await self._breaker.acall(lambda: self._primary.complete(request))
        except _FALLBACK_ON as exc:
            logger.warning("LLM provider unavailable, answering offline: %s", exc)
            response = await self._fallback.complete(request)
            response.content = self._with_notice(response.content)
            return response

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        try:
            self._breaker.before_call()
        except LLMCircuitOpenError as exc:
            logger.warning("LLM circuit open, streaming offline answer: %s", exc)
            async for token in self._offline_stream(request):
                yield token
            return
        started = False
        try:
            async for chunk in self._primary.stream(request):
                started = True
                yield chunk
        except _FALLBACK_ON as exc:
            self._breaker.record_failure()
            if started:
                raise
            logger.warning("LLM provider unavailable, streaming offline answer: %s", exc)
            async for token in self._offline_stream(request):
                yield token
            return
        except BaseException:
            self._breaker.abort()
            raise
        self._breaker.record_success()

    def _with_notice(self, text: str) -> str:
        if _DEMO_NOTICE in text:
            return text.replace(_DEMO_NOTICE, self._notice)
        return text + self._notice

    async def _offline_stream(self, request: LLMRequest) -> AsyncIterator[str]:
        response = await self._fallback.complete(request)
        for token in _TOKEN.findall(self._with_notice(response.content)):
            yield token
            if self._pace > 0:
                await asyncio.sleep(self._pace)
