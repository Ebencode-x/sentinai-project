"""Bridge between detection layer and AI analysis layer."""

from __future__ import annotations

import logging
import time

from src.core.config import settings
from src.core.metrics import metrics
from src.core.rate_limiter import llm_rate_limiter, pr_rate_limiter
from src.integrations import notifier
from src.integrations.github_client import GitHubClient
from src.integrations.llm_client import BaseLLMClient, StubLLMClient, build_llm_client
from src.models.events import LogIncident, RemediationSuggestion

logger = logging.getLogger(__name__)


class RemediationEngine:
    """Orchestrates incident-to-suggestion transformation."""

    def __init__(self, llm_client: BaseLLMClient | None = None) -> None:
        self._llm_client = llm_client or build_llm_client()
        self._stub = StubLLMClient()
        self._github = GitHubClient() if settings.github_token and settings.github_repo else None

    def suggest_fix(self, incident: LogIncident) -> RemediationSuggestion:
        """Ask the configured LLM client for remediation guidance."""
        if not llm_rate_limiter.consume():
            logger.warning("LLM rate limit exceeded — returning stub fallback.")
            base = self._stub.analyze_incident(incident)
            return base.model_copy(
                update={
                    "source": "fallback",
                    "provider_error": "Rate limit: too many LLM calls per minute.",
                    "confidence": 0.1,
                }
            )

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
        if self._github is not None and suggestion.proposed_patch:
            if not pr_rate_limiter.consume():
                logger.warning(
                    "PR rate limit exceeded — skipping GitHub PR for incident %s.",
                    incident.incident_id,
                )
                return suggestion
            try:
                pr_url = self._github.open_patch_pr(
                    incident_id=incident.incident_id,
                    trigger_line=incident.trigger_line,
                    summary=suggestion.summary,
                    proposed_patch=suggestion.proposed_patch,
                    test_guidance=suggestion.test_guidance or "",
                    confidence=suggestion.confidence,
                )
                suggestion = suggestion.model_copy(update={"pr_url": pr_url})
                if pr_url:
                    try:
                        notifier.notify(incident, suggestion)
                    except Exception as slack_exc:
                        logger.warning("Slack notification failed: %s", slack_exc)
            except Exception as exc:
                logger.warning("GitHub PR creation failed: %s", exc)
        return suggestion
