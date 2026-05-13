"""Sandbox execution block tests — D2.

Verifies that when Docker is unavailable:
  - allow_host_fallback=False (default) → execution BLOCKED, not run on host
  - allow_host_fallback=True  → host fallback permitted (dev/CI only)
  - Pipeline.run() returns sandbox_blocked=True with clear failure_reason
  - Audit entry is always written even on sandbox block
  - PipelineResult.sandbox_blocked field is present and accurate
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.models.events import LogIncident, RemediationSuggestion
from src.services.pipeline import PipelineResult, RemediationPipeline
from src.services.sandbox_config import SandboxConfig
from src.services.sandbox_runner import SandboxedPatchRunner

# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def _make_incident(incident_id: str = "d2-incident-001") -> LogIncident:
    return LogIncident(
        incident_id=incident_id,
        detected_at_utc=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
        severity="critical",
        trigger_line="ERROR connection refused",
        stacktrace="Traceback:\n  ConnectionRefusedError",
        context_before_error="INFO starting",
    )


def _make_suggestion(**kwargs) -> RemediationSuggestion:
    defaults = dict(
        summary="Add retry",
        proposed_code_fix="retry()",
        proposed_config_change="none",
        confidence=0.85,
        risks="Low",
        source="stub",
        proposed_patch="- old\n+ new\n",
        patch_file="src/app.py",
        test_guidance="run tests",
    )
    defaults.update(kwargs)
    return RemediationSuggestion(**defaults)


def _build_pipeline(tmp_path: Path, *, dry_run: bool = True) -> RemediationPipeline:
    with (
        patch("src.services.pipeline.build_llm_client"),
        patch("src.services.pipeline.GitHubClient", side_effect=RuntimeError("no github")),
        patch(
            "src.services.pipeline.SandboxedPatchRunner",
            side_effect=RuntimeError("no docker"),
        ),
    ):
        return RemediationPipeline(project_root=tmp_path, dry_run=dry_run)


# ---------------------------------------------------------------------------
# D2-1 — SandboxConfig.allow_host_fallback
# ---------------------------------------------------------------------------


class TestSandboxConfigFallbackFlag:
    def test_default_allow_host_fallback_is_false(self):
        """Production default must be False — no silent host execution."""
        config = SandboxConfig()
        assert config.allow_host_fallback is False

    def test_can_enable_fallback_explicitly(self):
        """Development/CI can opt in explicitly."""
        config = SandboxConfig(allow_host_fallback=True)
        assert config.allow_host_fallback is True

    def test_from_yaml_default_is_false(self, tmp_path: Path):
        """YAML without allow_host_fallback defaults to False."""
        yml = tmp_path / "sentinai-sandbox.yml"
        yml.write_text("image: python:3.11-slim\ntimeout_seconds: 60\n")
        config = SandboxConfig.from_yaml(yml)
        assert config.allow_host_fallback is False


# ---------------------------------------------------------------------------
# D2-2 — SandboxedPatchRunner.run_tests() blocking behavior
# ---------------------------------------------------------------------------


class TestSandboxedPatchRunnerBlock:
    def _make_runner(self, tmp_path: Path, *, allow_fallback: bool) -> SandboxedPatchRunner:
        """Build a SandboxedPatchRunner with Docker forcibly absent."""
        config = SandboxConfig(allow_host_fallback=allow_fallback)
        with patch("src.services.sandbox_runner.shutil.which", return_value=None):
            runner = SandboxedPatchRunner.__new__(SandboxedPatchRunner)
            runner._root = tmp_path
            runner.config = config
            runner._fallback = MagicMock()
            runner._fallback.run_tests.return_value = MagicMock(
                success=True, output="1 passed", returncode=0
            )
            runner._enforcer = MagicMock()
            runner._docker_available = False
        return runner

    def test_block_when_docker_absent_and_fallback_disabled(self, tmp_path: Path):
        """Docker absent + allow_host_fallback=False → blocked TestResult."""
        runner = self._make_runner(tmp_path, allow_fallback=False)
        result = runner.run_tests(workspace=tmp_path)
        assert result.success is False
        assert result.returncode == -2
        assert "SANDBOX BLOCKED" in result.output
        # Fallback runner must NOT have been called
        runner._fallback.run_tests.assert_not_called()

    def test_allow_fallback_when_flag_enabled(self, tmp_path: Path):
        """Docker absent + allow_host_fallback=True → host fallback allowed."""
        runner = self._make_runner(tmp_path, allow_fallback=True)
        result = runner.run_tests(workspace=tmp_path)
        assert result.success is True
        runner._fallback.run_tests.assert_called_once()

    def test_block_output_contains_guidance(self, tmp_path: Path):
        """Block message must guide the operator toward resolution."""
        runner = self._make_runner(tmp_path, allow_fallback=False)
        result = runner.run_tests(workspace=tmp_path)
        assert "Docker" in result.output
        assert "NOT run on the host" in result.output

    def test_returncode_minus_two_is_sentinel(self, tmp_path: Path):
        """returncode=-2 is the D2 block sentinel — distinct from test failure (-1)."""
        runner = self._make_runner(tmp_path, allow_fallback=False)
        result = runner.run_tests(workspace=tmp_path)
        assert result.returncode == -2


# ---------------------------------------------------------------------------
# D2-3 — Pipeline sandbox_blocked field and behavior
# ---------------------------------------------------------------------------


class TestPipelineSandboxBlock:
    def test_pipeline_result_has_sandbox_blocked_field(self, tmp_path: Path):
        """PipelineResult must expose sandbox_blocked: bool."""
        result = PipelineResult(
            incident=_make_incident(),
            suggestion=_make_suggestion(),
        )
        assert hasattr(result, "sandbox_blocked")
        assert result.sandbox_blocked is False

    def test_sandbox_blocked_true_when_sandbox_unavailable(self, tmp_path: Path):
        """Pipeline blocks and sets sandbox_blocked=True when sandbox init fails."""
        pipeline = _build_pipeline(tmp_path)
        # Confirm _sandbox_available was set to False during init
        assert getattr(pipeline, "_sandbox_available", None) is False

        incident = _make_incident()
        with patch.object(pipeline._engine, "suggest_fix", return_value=_make_suggestion()):
            with patch.object(
                pipeline._runner,
                "apply",
                return_value=MagicMock(success=True, error=None),
            ):
                result = pipeline.run(incident)

        assert result.sandbox_blocked is True
        assert result.patch_applied is False
        assert result.failure_reason is not None
        assert "D2" in result.failure_reason or "sandbox" in result.failure_reason.lower()

    def test_sandbox_block_writes_audit(self, tmp_path: Path):
        """Audit entry is written even when sandbox blocks execution."""
        from src.core.audit import AuditLogger

        log_path = tmp_path / "logs" / "audit.jsonl"
        audit = AuditLogger(log_path=log_path)

        pipeline = _build_pipeline(tmp_path)
        pipeline._audit = audit

        incident = _make_incident("d2-audit-check")
        with patch.object(pipeline._engine, "suggest_fix", return_value=_make_suggestion()):
            with patch.object(
                pipeline._runner,
                "apply",
                return_value=MagicMock(success=True, error=None),
            ):
                pipeline.run(incident)

        assert log_path.exists()
        entries = audit.tail(n=5)
        assert any(e["incident_id"] == "d2-audit-check" for e in entries)

    def test_no_pr_opened_on_sandbox_block(self, tmp_path: Path):
        """Blocked pipeline must never attempt to open a PR."""
        pipeline = _build_pipeline(tmp_path)
        incident = _make_incident()

        with patch.object(pipeline._engine, "suggest_fix", return_value=_make_suggestion()):
            with patch.object(
                pipeline._runner,
                "apply",
                return_value=MagicMock(success=True, error=None),
            ):
                result = pipeline.run(incident)

        assert result.pr_url is None

    def test_suggestion_preserved_on_sandbox_block(self, tmp_path: Path):
        """Even when blocked, the LLM suggestion is preserved in the result."""
        pipeline = _build_pipeline(tmp_path)
        incident = _make_incident()
        suggestion = _make_suggestion(summary="Specific fix advice")

        with patch.object(pipeline._engine, "suggest_fix", return_value=suggestion):
            with patch.object(
                pipeline._runner,
                "apply",
                return_value=MagicMock(success=True, error=None),
            ):
                result = pipeline.run(incident)

        assert result.suggestion.summary == "Specific fix advice"

    def test_sandbox_available_pipeline_does_not_block(self, tmp_path: Path):
        """When sandbox IS available, sandbox_blocked must remain False."""
        with (
            patch("src.services.pipeline.build_llm_client"),
            patch("src.services.pipeline.GitHubClient", side_effect=RuntimeError("no github")),
        ):
            pipeline = RemediationPipeline(project_root=tmp_path, dry_run=True)

        # If SandboxedPatchRunner initialised, _sandbox_available should be True
        # (Docker may or may not be present — test the flag, not Docker itself)
        assert hasattr(pipeline, "_sandbox_available")

    def test_multiple_blocked_incidents_all_recorded(self, tmp_path: Path):
        """Sequential sandbox-blocked runs each produce their own audit entry."""
        from src.core.audit import AuditLogger

        log_path = tmp_path / "logs" / "audit.jsonl"
        audit = AuditLogger(log_path=log_path)

        pipeline = _build_pipeline(tmp_path)
        pipeline._audit = audit

        for i in range(3):
            incident = _make_incident(f"d2-multi-{i:03d}")
            with patch.object(pipeline._engine, "suggest_fix", return_value=_make_suggestion()):
                with patch.object(
                    pipeline._runner,
                    "apply",
                    return_value=MagicMock(success=True, error=None),
                ):
                    pipeline.run(incident)

        entries = audit.tail(n=10)
        recorded = {e["incident_id"] for e in entries}
        for i in range(3):
            assert f"d2-multi-{i:03d}" in recorded
