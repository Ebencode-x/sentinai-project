"""Bridge between detection layer and AI analysis layer."""

from __future__ import annotations

from src.integrations.llm_client import BaseLLMClient, StubLLMClient
from src.models.events import LogIncident, RemediationSuggestion


class RemediationEngine:
    """Orchestrates incident-to-suggestion transformation."""

    def __init__(self, llm_client: BaseLLMClient | None = None) -> None:
        self._llm_client = llm_client or StubLLMClient()

    def suggest_fix(self, incident: LogIncident) -> RemediationSuggestion:
        """Ask the configured LLM client for remediation guidance."""
        return self._llm_client.analyze_incident(incident)

