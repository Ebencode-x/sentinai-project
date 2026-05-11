"""Abstract base types for LLM provider abstraction."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import StrEnum


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True, slots=True)
class LLMMessage:
    role: Role
    content: str

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise ValueError("LLMMessage content must not be empty.")


@dataclass(frozen=True, slots=True)
class LLMRequest:
    messages: tuple[LLMMessage, ...]
    model: str
    max_tokens: int = 1024
    temperature: float = 0.0
    stream: bool = False

    def __post_init__(self) -> None:
        if not self.messages:
            raise ValueError("LLMRequest must contain at least one message.")
        if not (0.0 <= self.temperature <= 2.0):
            raise ValueError("temperature must be in [0.0, 2.0].")
        if self.max_tokens < 1:
            raise ValueError("max_tokens must be >= 1.")


@dataclass(slots=True)
class LLMResponse:
    content: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    latency_ms: float = field(default=0.0)
    request_id: str = field(default="")

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class LLMProvider(ABC):
    """Base class for all LLM providers.

    Subclasses must implement `complete` and `stream`.
    All providers are stateless — credentials are injected at construction.
    """

    provider_name: str = "base"

    @abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Return a full completion for the given request."""

    @abstractmethod
    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Yield response tokens as they arrive."""

    def supports_streaming(self) -> bool:
        return True

    @staticmethod
    def _now_ms() -> float:
        return time.monotonic() * 1000
