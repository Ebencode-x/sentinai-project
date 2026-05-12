"""Autonomous Remediation Pipeline — #11 + A2/A3 Policy Gate + A4 Audit + C1/C2."""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from src.core.audit import AuditLogger, audit_logger
from src.integrations.github_client import GitHubClient
from src.integrations.llm_client import build_llm_client
from src.models.events import LogIncident, RemediationSuggestion
from src.services.patch_runner import PatchRunner
from src.services.policy_engine import Decision, PatchPolicyEngine
from src.services.remediation_engine import RemediationEngine
from src.services.sandbox_runner import SandboxedPatchRunner
from src.services.secret_sanitizer import SecretSanitizer

logger = logging.getLogger(__name__)

# Module-level singleton — one sanitizer instance, shared across all runs.
_sanitizer = SecretSanitizer()


@dataclass
class PipelineResult:
    """Full audit trail for one pipeline run."""

    incident: LogIncident
    suggestion: RemediationSuggestion
    patch_applied: bool = False
    tests_passed: bool | None = None
    pr_url: str | None = None
    failure_reason: str | None = None
    workspace: str | None = None
    policy_decision: str | None = None
    risk_tier: str | None = None
    audit_entry: dict | None = None
    # C1 — sanitization telemetry (count only, never plaintext)
    redactions_input_count: int = 0
    redactions_output_count: int = 0
    # C2 — sandbox telemetry
    sandbox_enforced: bool = False


@dataclass
class RemediationPipeline:
    """Orchestrates detect → sanitize → fix → sanitize → policy → sandbox → PR → audit."""

    project_root: Path = field(default_factory=Path.cwd)
    dry_run: bool = False
    policy_path: Path | None = None
    _engine: RemediationEngine = field(init=False)
    _runner: SandboxedPatchRunner = field(init=False)
    _fallback_runner: PatchRunner = field(init=False)
    _github: GitHubClient | None = field(init=False, default=None)
    _policy: PatchPolicyEngine = field(init=False)
    _audit: AuditLogger = field(init=False)

    def __post_init__(self) -> None:
        self._engine = RemediationEngine(llm_client=build_llm_client())
        # C2 — prefer sandboxed runner; falls back internally when Docker unavailable
        try:
            self._runner = SandboxedPatchRunner(project_root=self.project_root)
            self._fallback_runner = self._runner._fallback
            logger.info("[Pipeline] SandboxedPatchRunner initialised (C2)")
        except Exception as exc:
            logger.warning(
                "[Pipeline] SandboxedPatchRunner unavailable — using PatchRunner: %s", exc
            )
            plain = PatchRunner(project_root=self.project_root)
            self._runner = plain  # type: ignore[assignment]
            self._fallback_runner = plain
        policy_kwargs = {}
        if self.policy_path is not None:
            policy_kwargs["policy_path"] = self.policy_path
        self._policy = PatchPolicyEngine(**policy_kwargs)
        self._audit = audit_logger
        try:
            self._github = GitHubClient()
        except Exception as exc:
            logger.warning("GitHub client unavailable — PR stage disabled: %s", exc)
            self._github = None

    def run(self, incident: LogIncident) -> PipelineResult:
        result = PipelineResult(
            incident=incident,
            suggestion=RemediationSuggestion(
                summary="",
                proposed_code_fix="",
                proposed_config_change="",
                confidence=0.0,
                risks="",
                source="stub",
            ),
        )

        # ----------------------------------------------------------------
        # Stage 0 — Sanitize incident fields before LLM sees them
        # ----------------------------------------------------------------
        logger.info("[Pipeline] Stage 0: sanitizing incident input")
        incident, redactions_in = _sanitize_incident(incident)
        result.redactions_input_count = redactions_in
        if redactions_in:
            logger.warning("[Pipeline] %d secret(s) redacted from incident input", redactions_in)

        # ----------------------------------------------------------------
        # Stage 1 — Generate suggestion via LLM
        # ----------------------------------------------------------------
        logger.info("[Pipeline] Stage 1: generating for %s", incident.incident_id)
        try:
            suggestion = self._engine.suggest_fix(incident)
        except Exception as exc:
            result.failure_reason = f"LLM stage failed: {exc}"
            logger.error("[Pipeline] LLM stage failed: %s", exc)
            self._record_audit(result)
            return result

        # ----------------------------------------------------------------
        # Stage 1.5 — Sanitize LLM output (defense in depth)
        # ----------------------------------------------------------------
        logger.info("[Pipeline] Stage 1.5: sanitizing LLM output")
        suggestion, redactions_out = _sanitize_suggestion(suggestion)
        result.redactions_output_count = redactions_out
        if redactions_out:
            logger.warning("[Pipeline] %d secret(s) redacted from LLM output", redactions_out)

        result.suggestion = suggestion

        if not suggestion.proposed_patch or not suggestion.patch_file:
            logger.info("[Pipeline] No patch — suggestion only.")
            self._record_audit(result)
            return result

        # ----------------------------------------------------------------
        # Stage 2b — Policy Gate
        # ----------------------------------------------------------------
        logger.info("[Pipeline] Stage 2b: policy gate")
        policy_result = self._policy.check(
            patch=suggestion.proposed_patch,
            patch_file=suggestion.patch_file,
        )
        result.policy_decision = policy_result.decision.value
        result.risk_tier = policy_result.risk_tier

        if policy_result.decision is Decision.BLOCK:
            reasons = "; ".join(policy_result.reasons)
            result.failure_reason = f"Policy BLOCK: {reasons}"
            logger.warning("[Pipeline] Policy blocked: %s", reasons)
            result.suggestion = suggestion.model_copy(
                update={"provider_error": result.failure_reason}
            )
            self._record_audit(result)
            return result

        if policy_result.decision is Decision.REVIEW:
            reasons = "; ".join(policy_result.reasons)
            result.failure_reason = (
                f"Policy REVIEW: human approval required "
                f"(risk={policy_result.risk_tier}). Reasons: {reasons}"
            )
            logger.info("[Pipeline] Policy REVIEW: %s", reasons)
            result.suggestion = suggestion.model_copy(
                update={"provider_error": result.failure_reason}
            )
            self._record_audit(result)
            return result

        logger.info("[Pipeline] Policy ALLOW — risk=%s", policy_result.risk_tier)

        # ----------------------------------------------------------------
        # Stage 2 — Apply patch
        # ----------------------------------------------------------------
        logger.info("[Pipeline] Stage 2: applying patch")
        with tempfile.TemporaryDirectory(prefix="sentinai_") as tmpdir:
            result.workspace = tmpdir
            patch_result = self._runner.apply(
                patch=suggestion.proposed_patch,
                patch_file=suggestion.patch_file,
                workspace=Path(tmpdir),
            )

            if not patch_result.success:
                result.failure_reason = f"Patch apply failed: {patch_result.error}"
                logger.warning("[Pipeline] Patch apply failed: %s", patch_result.error)
                result.suggestion = suggestion.model_copy(
                    update={"provider_error": result.failure_reason}
                )
                self._record_audit(result)
                return result

            result.patch_applied = True
            result.sandbox_enforced = isinstance(self._runner, SandboxedPatchRunner)

            # Stage 3 — Run tests
            logger.info("[Pipeline] Stage 3: running pytest")
            test_result = self._runner.run_tests(workspace=Path(tmpdir))
            result.tests_passed = test_result.success

            if not test_result.success:
                result.failure_reason = (
                    f"Tests failed — discarding. Output: {test_result.output[:500]}"
                )
                logger.warning("[Pipeline] Tests failed — patch discarded.")
                result.suggestion = suggestion.model_copy(
                    update={
                        "provider_error": result.failure_reason,
                        "confidence": min(suggestion.confidence, 0.2),
                    }
                )
                self._record_audit(result)
                return result

            logger.info("[Pipeline] Tests passed.")

        # ----------------------------------------------------------------
        # Stage 4 — Open PR
        # ----------------------------------------------------------------
        if self.dry_run:
            logger.info("[Pipeline] dry_run=True — skipping PR.")
            self._record_audit(result)
            return result

        if self._github is None:
            logger.info("[Pipeline] GitHub unavailable — skipping PR.")
            self._record_audit(result)
            return result

        logger.info("[Pipeline] Stage 4: opening PR")
        try:
            pr_url = self._github.open_patch_pr(
                incident_id=incident.incident_id,
                trigger_line=incident.trigger_line,
                summary=suggestion.summary,
                proposed_patch=suggestion.proposed_patch,
                test_guidance=suggestion.test_guidance or "",
                confidence=suggestion.confidence,
                patch_file=suggestion.patch_file,
            )
            result.pr_url = pr_url
            result.suggestion = suggestion.model_copy(update={"pr_url": pr_url})
            logger.info("[Pipeline] PR opened: %s", pr_url)
        except Exception as exc:
            logger.warning("[Pipeline] PR creation failed: %s", exc)
            result.failure_reason = f"PR stage failed: {exc}"

        self._record_audit(result)
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_audit(self, result: PipelineResult) -> None:
        sug = result.suggestion
        try:
            entry = self._audit.record(
                incident_id=result.incident.incident_id,
                model=getattr(sug, "model", "unknown"),
                provider=sug.source,
                patch_file=sug.patch_file,
                patch=sug.proposed_patch,
                policy_decision=result.policy_decision,
                risk_tier=result.risk_tier,
                review_required=result.policy_decision == "review",
                patch_applied=result.patch_applied,
                tests_passed=result.tests_passed,
                pr_url=result.pr_url,
                failure_reason=result.failure_reason,
                confidence=sug.confidence,
                source=sug.source,
            )
            result.audit_entry = entry
        except Exception as exc:
            logger.error("[Pipeline] Audit record failed: %s", exc)


# ---------------------------------------------------------------------------
# Module-level sanitization helpers
# ---------------------------------------------------------------------------


def _sanitize_incident(incident: LogIncident) -> tuple[LogIncident, int]:
    """Sanitize all free-text fields of an incident.

    Returns a new LogIncident with secrets redacted and the total
    redaction count (for telemetry — no plaintext ever logged).
    """
    fields_to_sanitize = {
        "trigger_line": incident.trigger_line,
        "stacktrace": incident.stacktrace or "",
        "context_before_error": incident.context_before_error or "",
    }

    updates: dict[str, str] = {}
    total_redactions = 0

    for field_name, value in fields_to_sanitize.items():
        if not value:
            continue
        result = _sanitizer.sanitize(value)
        updates[field_name] = result.text
        total_redactions += len(result.redactions)

    if not updates:
        return incident, 0

    return incident.model_copy(update=updates), total_redactions


def _sanitize_suggestion(
    suggestion: RemediationSuggestion,
) -> tuple[RemediationSuggestion, int]:
    """Sanitize free-text fields of an LLM suggestion (defense in depth).

    Returns a new RemediationSuggestion with secrets redacted and the
    total redaction count.
    """
    fields_to_sanitize = {
        "summary": suggestion.summary or "",
        "proposed_patch": suggestion.proposed_patch or "",
        "risks": suggestion.risks or "",
        "test_guidance": suggestion.test_guidance or "",
    }

    updates: dict[str, str] = {}
    total_redactions = 0

    for field_name, value in fields_to_sanitize.items():
        if not value:
            continue
        result = _sanitizer.sanitize(value)
        updates[field_name] = result.text
        total_redactions += len(result.redactions)

    if not updates:
        return suggestion, 0

    return suggestion.model_copy(update=updates), total_redactions
