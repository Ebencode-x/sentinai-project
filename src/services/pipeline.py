"""Autonomous Remediation Pipeline — #11 + A2/A3 Policy Gate.

Flow:
    1. Detect incident (LogWatcher)
    2. Generate fix (LLM via RemediationEngine)
    2b. Policy Gate (A2/A3) — BLOCK/REVIEW/ALLOW before any file is touched
    3. Apply patch in isolated temp workspace
    4. Run pytest in workspace
    5. Tests pass  → open GitHub PR
    6. Tests fail  → discard patch, return suggestion with failure note
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from src.integrations.github_client import GitHubClient
from src.integrations.llm_client import build_llm_client
from src.models.events import LogIncident, RemediationSuggestion
from src.services.patch_runner import PatchRunner
from src.services.policy_engine import Decision, PatchPolicyEngine
from src.services.remediation_engine import RemediationEngine

logger = logging.getLogger(__name__)


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


@dataclass
class RemediationPipeline:
    """Orchestrates the full detect → fix → policy → test → PR loop.

    Parameters
    ----------
    project_root:
        Absolute path to the repo root.
    dry_run:
        When True the pipeline runs every stage but skips PR creation.
    policy_path:
        Override path to sentinai-policy.yml. Defaults to repo root.
    """

    project_root: Path = field(default_factory=Path.cwd)
    dry_run: bool = False
    policy_path: Path | None = None
    _engine: RemediationEngine = field(init=False)
    _runner: PatchRunner = field(init=False)
    _github: GitHubClient | None = field(init=False, default=None)
    _policy: PatchPolicyEngine = field(init=False)

    def __post_init__(self) -> None:
        self._engine = RemediationEngine(llm_client=build_llm_client())
        self._runner = PatchRunner(project_root=self.project_root)
        policy_kwargs = {}
        if self.policy_path is not None:
            policy_kwargs["policy_path"] = self.policy_path
        self._policy = PatchPolicyEngine(**policy_kwargs)
        try:
            self._github = GitHubClient()
        except Exception as exc:
            logger.warning("GitHub client unavailable — PR stage disabled: %s", exc)
            self._github = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, incident: LogIncident) -> PipelineResult:
        """Execute the full remediation pipeline for one incident."""
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

        # Stage 1 — Generate suggestion
        logger.info(
            "[Pipeline] Stage 1: generating suggestion for %s",
            incident.incident_id,
        )
        try:
            suggestion = self._engine.suggest_fix(incident)
        except Exception as exc:
            result.failure_reason = f"LLM stage failed: {exc}"
            logger.error("[Pipeline] LLM stage failed: %s", exc)
            return result

        result.suggestion = suggestion

        # Stage 2 — Apply patch
        if not suggestion.proposed_patch or not suggestion.patch_file:
            logger.info("[Pipeline] No patch to apply — pipeline complete (suggestion only).")
            return result

        # Stage 2b — Policy Gate (A2/A3 Decision Firewall)
        logger.info("[Pipeline] Stage 2b: policy gate check")
        policy_result = self._policy.check(
            patch=suggestion.proposed_patch,
            patch_file=suggestion.patch_file,
        )
        result.policy_decision = policy_result.decision.value
        result.risk_tier = policy_result.risk_tier

        if policy_result.decision is Decision.BLOCK:
            reasons = "; ".join(policy_result.reasons)
            result.failure_reason = f"Policy BLOCK: {reasons}"
            logger.warning("[Pipeline] Policy blocked patch: %s", reasons)
            result.suggestion = suggestion.model_copy(
                update={"provider_error": result.failure_reason}
            )
            return result

        if policy_result.decision is Decision.REVIEW:
            reasons = "; ".join(policy_result.reasons)
            logger.info("[Pipeline] Policy REVIEW required: %s", reasons)
            result.failure_reason = (
                f"Policy REVIEW: human approval required "
                f"(risk={policy_result.risk_tier}). Reasons: {reasons}"
            )
            result.suggestion = suggestion.model_copy(
                update={"provider_error": result.failure_reason}
            )
            return result

        logger.info(
            "[Pipeline] Policy ALLOW — risk=%s, proceeding.",
            policy_result.risk_tier,
        )

        logger.info("[Pipeline] Stage 2: applying patch to temp workspace")
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
                return result

            result.patch_applied = True
            logger.info("[Pipeline] Patch applied successfully.")

            # Stage 3 — Run tests
            logger.info("[Pipeline] Stage 3: running pytest in workspace")
            test_result = self._runner.run_tests(workspace=Path(tmpdir))
            result.tests_passed = test_result.success

            if not test_result.success:
                result.failure_reason = (
                    f"Tests failed after patch — discarding. Output: {test_result.output[:500]}"
                )
                logger.warning("[Pipeline] Tests failed — patch discarded.")
                result.suggestion = suggestion.model_copy(
                    update={
                        "provider_error": result.failure_reason,
                        "confidence": min(suggestion.confidence, 0.2),
                    }
                )
                return result

            logger.info("[Pipeline] Tests passed.")

        # Stage 4 — Open PR
        if self.dry_run:
            logger.info("[Pipeline] dry_run=True — skipping PR creation.")
            return result

        if self._github is None:
            logger.info("[Pipeline] GitHub unavailable — skipping PR.")
            return result

        logger.info("[Pipeline] Stage 4: opening GitHub PR")
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

        return result
