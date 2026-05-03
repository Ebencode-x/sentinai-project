"""LLM integration scaffold for incident analysis.

This module intentionally contains a provider-agnostic interface and a
placeholder implementation. Swap `StubLLMClient` with concrete providers
(OpenAI, Anthropic, etc.) in production.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.models.events import LogIncident, RemediationSuggestion


class BaseLLMClient(ABC):
    """Abstract interface for analyzing incidents with an LLM."""

    @abstractmethod
    def analyze_incident(self, incident: LogIncident) -> RemediationSuggestion:
        """Return a remediation suggestion generated from incident context."""
        raise NotImplementedError


class StubLLMClient(BaseLLMClient):
    """Safe local placeholder that mimics an AI response.

    Why this exists:
    - Allows end-to-end demos without external API keys.
    - Keeps architecture ready for provider replacement.
    """

    def analyze_incident(self, incident: LogIncident) -> RemediationSuggestion:
        return RemediationSuggestion(
            summary="Potential unhandled exception detected. Add guard clauses and improve error handling.",
            proposed_code_fix=(
                "Wrap failing logic in try/except, validate nullable values before use, "
                "and return controlled HTTP errors instead of raw tracebacks."
            ),
            proposed_config_change=(
                "Set production log level to INFO and route stack traces to secure sink; "
                "consider tuning worker timeout if failures are timeout-related."
            ),
            confidence=0.62,
            risks="Suggestion is heuristic. Validate with tests before rollout.",
        )

