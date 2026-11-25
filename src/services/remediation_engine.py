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
from src.integrations.patch_utils import PatchRejected, parse_single_file_patch
from src.models.events import LogIncident, RemediationSuggestion
from src.services.incident_redaction import redact_incident
from src.services.policy_engine import PatchPolicyEngine

logger = logging.getLogger(__name__)


class RemediationEngine:
    """Orchestrates incident-to-suggestion transformation."""

    def __init__(
        self,
        llm_client: BaseLLMClient | None = None,
        enforce_policy: bool = True,
        policy: PatchPolicyEngine | None = None,
    ) -> None:
        self._llm_client = llm_client or build_llm_client()
        self._stub = StubLLMClient()
        # Every proposed patch goes through the policy before any PR. Fail closed:
        # when the policy cannot be loaded, every patch is withheld.
        self._enforce_policy = enforce_policy
        self._policy = policy
        self._policy_error: str | None = None
        if enforce_policy and policy is None:
            try:
                self._policy = PatchPolicyEngine(require_policy=True)
            except Exception as exc:
                self._policy_error = f"{type(exc).__name__}: {exc}"
                logger.error("Patch policy unavailable, all patches will be withheld: %s", exc)
        self._github: GitHubClient | None = None
        if settings.github_token and settings.github_repo:
            try:
                self._github = GitHubClient()
            except Exception as exc:
                logger.warning("GitHub client unavailable, PR and rollback disabled: %s", exc)

    @property
    def github_client(self) -> GitHubClient | None:
        return self._github

    @staticmethod
    def _withhold(
        suggestion: RemediationSuggestion, incident_id: str, reason: str
    ) -> RemediationSuggestion:
        logger.warning("Patch withheld for incident %s: %s", incident_id, reason)
        return suggestion.model_copy(
            update={"proposed_patch": None, "provider_error": f"Policy BLOCK: {reason}"}
        )

    def _apply_policy_gate(
        self, suggestion: RemediationSuggestion, incident_id: str
    ) -> tuple[RemediationSuggestion, bool]:
        """Run the patch policy on a proposed diff; returns (suggestion, needs_review).

        The file comes from the diff header via parse_single_file_patch, the same
        parser open_patch_pr uses, so the policy and the PR always see one file.
        Text that is not a usable single-file diff is left alone: open_patch_pr
        rejects it with the same parser, so it can never reach the repository.
        A policy that is missing or crashes withholds the patch.
        """
        if not self._enforce_policy or not suggestion.proposed_patch:
            return suggestion, False
        try:
            patch_file, patch_set = parse_single_file_patch(suggestion.proposed_patch)
        except PatchRejected:
            return suggestion, False
        if self._policy is None:
            reason = f"policy unavailable ({self._policy_error})"
            return self._withhold(suggestion, incident_id, reason), False
        try:
            result = self._policy.check(
                patch=suggestion.proposed_patch,
                patch_file=patch_file,
                files_changed=len(patch_set),
            )
        except Exception as exc:
            logger.exception("Patch policy check crashed for incident %s", incident_id)
            reason = f"policy check failed ({type(exc).__name__})"
            return self._withhold(suggestion, incident_id, reason), False
        reasons = "; ".join(result.reasons)
        if result.blocked:
            return self._withhold(suggestion, incident_id, reasons), False
        if result.requires_review:
            logger.info("Patch needs human review for incident %s: %s", incident_id, reasons)
            note = (
                f"Policy REVIEW: human approval required (risk={result.risk_tier}). "
                f"Reasons: {reasons}"
            )
            return suggestion.model_copy(update={"provider_error": note}), True
        return suggestion, False

    def suggest_fix(
        self, incident: LogIncident, autonomy_mode: str = "propose_only"
    ) -> RemediationSuggestion:
        """Ask the configured LLM client for remediation guidance."""
        incident, redacted = redact_incident(incident)
        if redacted:
            logger.warning(
                "%d secret(s) redacted before analysis of incident %s",
                redacted,
                incident.incident_id,
            )
        if not llm_rate_limiter.consume():
            logger.warning("LLM rate limit exceeded — returning stub fallback.")
            base = self._stub.analyze_incident(incident)
            return base.model_copy(
                update={
                    "source": "fallback",
                    "provider_error": "Rate limit: too many LLM calls per minute.",
                    "model": self._stub.model_name,
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
                    "model": self._stub.model_name,
                    "summary": f"{base.summary} (Provider error; heuristic fallback.)",
                    "confidence": min(base.confidence, 0.35),
                }
            )
        finally:
            latency_ms = (time.perf_counter() - t0) * 1000
            if suggestion is not None:
                metrics.record(latency_ms=latency_ms, source=suggestion.source)
        suggestion = suggestion.model_copy(
            update={
                "autonomy_mode": autonomy_mode,
                "model": suggestion.model or getattr(self._llm_client, "model_name", "unknown"),
            }
        )

        suggestion, needs_review = self._apply_policy_gate(suggestion, incident.incident_id)
        if needs_review:
            return suggestion.model_copy(update={"awaiting_approval": True})

        if suggestion.proposed_patch and autonomy_mode != "auto_pr":
            logger.info(
                "Autonomy mode is '%s' — withholding auto-PR for incident %s.",
                autonomy_mode,
                incident.incident_id,
            )
            return suggestion.model_copy(update={"awaiting_approval": True})

        if self._github is not None and suggestion.proposed_patch:
            if not pr_rate_limiter.consume():
                logger.warning(
                    "PR rate limit exceeded — skipping GitHub PR for incident %s.",
                    incident.incident_id,
                )
                return suggestion
            try:
                pr_result = self._github.open_patch_pr(
                    incident_id=incident.incident_id,
                    trigger_line=incident.trigger_line,
                    summary=suggestion.summary,
                    proposed_patch=suggestion.proposed_patch,
                    test_guidance=suggestion.test_guidance or "",
                    confidence=suggestion.confidence,
                )
                if pr_result:
                    suggestion = suggestion.model_copy(
                        update={
                            "pr_url": pr_result.get("pr_url"),
                            "pr_number": pr_result.get("pr_number"),
                            "patch_file": pr_result.get("patch_file"),
                            "before_sha": pr_result.get("before_sha"),
                            "branch_name": pr_result.get("branch_name"),
                        }
                    )
                    try:
                        notifier.notify(incident, suggestion)
                    except Exception as slack_exc:
                        logger.warning("Slack notification failed: %s", slack_exc)
            except Exception as exc:
                logger.warning("GitHub PR creation failed: %s", exc)
        return suggestion
