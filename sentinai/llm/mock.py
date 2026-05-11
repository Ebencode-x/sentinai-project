"""In-process mock provider — deterministic, zero-network, for tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from sentinai.llm.base import LLMProvider, LLMRequest, LLMResponse


@dataclass
class MockProvider(LLMProvider):
    """Configurable mock for unit tests.

    Usage::

        provider = MockProvider(response="hello")
        resp = await provider.complete(request)
        assert resp.content == "hello"
    """

    provider_name: str = "mock"
    response: str = "mock-response"
    raise_on_complete: Exception | None = None
    raise_on_stream: Exception | None = None
    calls: list[LLMRequest] = field(default_factory=list)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        if self.raise_on_complete is not None:
            raise self.raise_on_complete
        return LLMResponse(
            content=self.response,
            model=request.model,
            provider=self.provider_name,
            input_tokens=10,
            output_tokens=len(self.response.split()),
            latency_ms=0.1,
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        self.calls.append(request)
        if self.raise_on_stream is not None:
            raise self.raise_on_stream
        for word in self.response.split():
            yield word + " "
