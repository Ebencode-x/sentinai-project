"""Provider factory — reads env vars, returns ready-to-use LLMProvider."""

from __future__ import annotations

import os

from sentinai.llm.base import LLMProvider
from sentinai.llm.exceptions import LLMProviderError

_REGISTRY: dict[str, type[LLMProvider]] = {}


def register_provider(name: str, cls: type[LLMProvider]) -> None:
    _REGISTRY[name.lower()] = cls


def build_provider(provider: str | None = None) -> LLMProvider:
    """Construct and return the configured LLM provider.

    Provider selection order:
    1. ``provider`` argument (if given)
    2. ``SENTINAI_LLM_PROVIDER`` env var
    3. Falls back to ``anthropic``

    API keys are read from env vars — never from arguments.
    """
    name = (provider or os.getenv("SENTINAI_LLM_PROVIDER", "anthropic")).lower()

    # Lazy-register built-ins on first call
    if not _REGISTRY:
        _register_builtins()

    cls = _REGISTRY.get(name)
    if cls is None:
        available = ", ".join(sorted(_REGISTRY))
        raise LLMProviderError(f"Unknown LLM provider {name!r}. Available: {available}")
    return _instantiate(name, cls)


def _register_builtins() -> None:
    from sentinai.llm.anthropic import AnthropicProvider  # noqa: PLC0415
    from sentinai.llm.mock import MockProvider  # noqa: PLC0415
    from sentinai.llm.smart_stub import SmartStubProvider  # noqa: PLC0415

    register_provider("anthropic", AnthropicProvider)
    register_provider("mock", MockProvider)
    register_provider("smart_stub", SmartStubProvider)


def _instantiate(name: str, cls: type[LLMProvider]) -> LLMProvider:
    if name == "anthropic":
        key = os.getenv("ANTHROPIC_API_KEY", "")
        if not key:
            from sentinai.llm.smart_stub import SmartStubProvider  # noqa: PLC0415
            return SmartStubProvider()
        return cls(api_key=key)  # type: ignore[call-arg]
    if name == "mock":
        return cls()  # type: ignore[call-arg]
    if name == "smart_stub":
        return cls()  # type: ignore[call-arg]
    raise LLMProviderError(f"No instantiation rule for provider {name!r}.")
