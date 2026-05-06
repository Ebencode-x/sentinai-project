"""Bridge between detection layer and AI analysis layer."""

from __future__ import annotations

import logging
import time

from src.core.metrics import metrics
from src.integrations.llm_client import BaseLLMClient, StubLLMClient, build_llm_client
from src.models.events import LogIncident, RemediationSuggestion

logger = logging.getLogger(__name__)


class RemediationEngine:
    """Orchestrates incident-to-suggestion transformation."""

    def __init__(self, llm_client: BaseLLMClient | None = None) -> None:
        self._llm_client = llm_client or build_llm_client()
        self._stub = StubLLMClient()

    def suggest_fix(self, incident: LogIncident) -> RemediationSuggestion:
        """Ask the configured LLM client for remediation guidance."""
        t0 = time.perf_counter()
        suggestion = None
        try:
            suggestion = self._llm_client.analyze_incident(incident)
        except Exception as exc:
            logger.warning("LLM analysis failed; returning stub-based fallback: %s", exc)
            base = self._stub.analyze_incident(incident)
            suggestion = base.model_copy(
                update={
                    "source": "fallback",
                    "provider_error": str(exc)[:4000],
                    "summary": f"{base.summary} (Provider error; heuristic fallback.)",
                    "confidence": min(base.confidence, 0.35),
                }
            )
        finally:
            latency_ms = (time.perf_counter() - t0) * 1000
            if suggestion is not None:
                metrics.record(latency_ms=latency_ms, source=suggestion.source)
        return suggestion
