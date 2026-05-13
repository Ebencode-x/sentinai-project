"""End-to-end pipeline test — C3.

Runs a complete fake incident through the full pipeline:
    sanitize → LLM (stub) → sanitize → policy → sandbox/patch → audit

No manual intervention required.
No real LLM calls, no Docker, no GitHub — all external I/O is stubbed.
Assertions confirm every stage fires and output flows correctly.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.models.events import LogIncident, RemediationSuggestion
from src.services.pipeline import PipelineResult, RemediationPipeline


# ---------------------------------------------------------------------------
# Fake incident factory
# ---------------------------------------------------------------------------

def _make_incident(
    *,
    trigger_line: str = "ERROR database connection refused at host 192.168.1.1",
    stacktrace: str = (
        "Traceback (most recent call last):\n"
        '  File "app.py", line 42, in connect\n'
        "  ConnectionRefusedError: [Errno 111] Connection refused"
    ),
    context: str = "INFO starting worker\nINFO connecting to database",
) -> LogIncident:
    return LogIncident(
        incident_id="test-incident-c3-001",
        detected_at_utc=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        severity="critical",
        trigger_line=trigger_line,
        stacktrace=stacktrace,
        context_before_error=context,
    )


def _make_suggestion(**kwargs) -> RemediationSuggestion:
    defaults = dict(
        summary="Retry with exponential backoff",
        proposed_code_fix="Add retry logic",
        proposed_config_change="none",
        confidence=0.85,
        risks="Low",
        source="stub",
        proposed_patch="- old line\n+ new line\n",
        patch_file="app.py",
        test_guidance="Run test_connect.py",
    )
    defaults.update(kwargs)
    return RemediationSuggestion(**defaults)


# ---------------------------------------------------------------------------
# Helpers — build pipeline with all external I/O mocked
# ---------------------------------------------------------------------------

def _build_pipeline(tmp_path: Path) -> RemediationPipeline:
    """Construct a RemediationPipeline with external services stubbed out."""
    with (
        patch("src.services.pipeline.build_llm_client"),
        patch("src.services.pipeline.GitHubClient", side_effect=RuntimeError("no github")),
        patch("src.services.pipeline.SandboxedPatchRunner", side_effect=RuntimeError("no docker")),
    ):
        return RemediationPipeline(project_root=tmp_path, dry_run=True)


# ---------------------------------------------------------------------------
# C3 — Stage flow tests
# ---------------------------------------------------------------------------


class TestEndToEndFakeIncident:
    """Full pipeline run with a fake incident — no real I/O."""

    def test_pipeline_returns_pipeline_result(self, tmp_path: Path):
        pipeline = _build_pipeline(tmp_path)
        incident = _make_incident()

        with patch.object(pipeline._engine, "suggest_fix", return_value=_make_suggestion()):
            with patch.object(pipeline._runner, "apply") as mock_apply:
                with patch.object(pipeline._runner, "run_tests") as mock_tests:
                    mock_apply.return_value = MagicMock(success=True, error=None)
                    mock_tests.return_value = MagicMock(success=True, output="1 passed")
                    result = pipeline.run(incident)

        assert isinstance(result, PipelineResult)

    def test_suggestion_stage_fires(self, tmp_path: Path):
        pipeline = _build_pipeline(tmp_path)
        incident = _make_incident()
        suggestion = _make_suggestion()

        with patch.object(pipeline._engine, "suggest_fix", return_value=suggestion) as mock_llm:
            with patch.object(pipeline._runner, "apply", return_value=MagicMock(success=True)):
                with patch.object(
                    pipeline._runner, "run_tests", return_value=MagicMock(success=True, output="")
                ):
                    pipeline.run(incident)

        mock_llm.assert_called_once()
        call_incident = mock_llm.call_args[0][0]
        # Incident passed to LLM must have been sanitized (same id, clean fields)
        assert call_incident.incident_id == incident.incident_id

    def test_sanitizer_runs_on_incident_input(self, tmp_path: Path):
        """Incident containing a secret gets redacted before LLM sees it."""
        pipeline = _build_pipeline(tmp_path)
        # Embed a fake AWS key in trigger line
        dirty_trigger = "ERROR AKIAIOSFODNN7EXAMPLE connection refused"
        incident = _make_incident(trigger_line=dirty_trigger)

        captured: list[LogIncident] = []

        def capture_incident(inc: LogIncident) -> RemediationSuggestion:
            captured.append(inc)
            return _make_suggestion(proposed_patch=None, patch_file=None)

        with patch.object(pipeline._engine, "suggest_fix", side_effect=capture_incident):
            result = pipeline.run(incident)

        assert captured, "suggest_fix was never called"
        sanitized_trigger = captured[0].trigger_line
        assert "AKIAIOSFODNN7EXAMPLE" not in sanitized_trigger
        assert "[REDACTED" in sanitized_trigger
        assert result.redactions_input_count >= 1

    def test_sanitizer_runs_on_llm_output(self, tmp_path: Path):
        """LLM output containing a secret gets redacted before policy/patch."""
        pipeline = _build_pipeline(tmp_path)
        incident = _make_incident()
        # LLM accidentally leaks an AWS key in its summary
        dirty_suggestion = _make_suggestion(
            summary="Fix by using key AKIAIOSFODNN7EXAMPLE",
            proposed_patch=None,
            patch_file=None,
        )

        with patch.object(pipeline._engine, "suggest_fix", return_value=dirty_suggestion):
            result = pipeline.run(incident)

        assert "AKIAIOSFODNN7EXAMPLE" not in result.suggestion.summary
        assert result.redactions_output_count >= 1

    def test_policy_stage_fires(self, tmp_path: Path):
        """Policy gate is evaluated before patch is applied."""
        pipeline = _build_pipeline(tmp_path)
        incident = _make_incident()

        with patch.object(pipeline._engine, "suggest_fix", return_value=_make_suggestion()):
            with patch.object(pipeline._policy, "check", wraps=pipeline._policy.check) as mock_policy:
                with patch.object(
                    pipeline._runner, "apply", return_value=MagicMock(success=True)
                ):
                    with patch.object(
                        pipeline._runner,
                        "run_tests",
                        return_value=MagicMock(success=True, output=""),
                    ):
                        pipeline.run(incident)

        mock_policy.assert_called_once()

    def test_policy_decision_recorded_in_result(self, tmp_path: Path):
        pipeline = _build_pipeline(tmp_path)
        incident = _make_incident()

        with patch.object(pipeline._engine, "suggest_fix", return_value=_make_suggestion()):
            with patch.object(
                pipeline._runner, "apply", return_value=MagicMock(success=True)
            ):
                with patch.object(
                    pipeline._runner,
                    "run_tests",
                    return_value=MagicMock(success=True, output=""),
                ):
                    result = pipeline.run(incident)

        assert result.policy_decision in {"allow", "review", "block"}

    def test_audit_entry_recorded(self, tmp_path: Path):
        pipeline = _build_pipeline(tmp_path)
        incident = _make_incident()

        with patch.object(pipeline._engine, "suggest_fix", return_value=_make_suggestion()):
            with patch.object(
                pipeline._runner, "apply", return_value=MagicMock(success=True)
            ):
                with patch.object(
                    pipeline._runner,
                    "run_tests",
                    return_value=MagicMock(success=True, output=""),
                ):
                    result = pipeline.run(incident)

        assert result.audit_entry is not None
        assert result.audit_entry["incident_id"] == "test-incident-c3-001"

    def test_no_patch_path_returns_suggestion_only(self, tmp_path: Path):
        """If LLM returns no patch, pipeline exits cleanly after suggestion."""
        pipeline = _build_pipeline(tmp_path)
        incident = _make_incident()
        no_patch = _make_suggestion(proposed_patch=None, patch_file=None)

        with patch.object(pipeline._engine, "suggest_fix", return_value=no_patch):
            result = pipeline.run(incident)

        assert result.patch_applied is False
        assert result.failure_reason is None

    def test_llm_failure_returns_failure_reason(self, tmp_path: Path):
        pipeline = _build_pipeline(tmp_path)
        incident = _make_incident()

        with patch.object(
            pipeline._engine, "suggest_fix", side_effect=RuntimeError("LLM timeout")
        ):
            result = pipeline.run(incident)

        assert result.failure_reason is not None
        assert "LLM" in result.failure_reason

    def test_dry_run_skips_pr(self, tmp_path: Path):
        pipeline = _build_pipeline(tmp_path)
        assert pipeline.dry_run is True
        incident = _make_incident()

        with patch.object(pipeline._engine, "suggest_fix", return_value=_make_suggestion()):
            with patch.object(
                pipeline._runner, "apply", return_value=MagicMock(success=True)
            ):
                with patch.object(
                    pipeline._runner,
                    "run_tests",
                    return_value=MagicMock(success=True, output=""),
                ):
                    result = pipeline.run(incident)

        assert result.pr_url is None

    def test_result_telemetry_fields_present(self, tmp_path: Path):
        """PipelineResult exposes C1/C2 telemetry fields."""
        pipeline = _build_pipeline(tmp_path)
        incident = _make_incident()

        with patch.object(
            pipeline._engine, "suggest_fix", return_value=_make_suggestion(proposed_patch=None, patch_file=None)
        ):
            result = pipeline.run(incident)

        assert hasattr(result, "redactions_input_count")
        assert hasattr(result, "redactions_output_count")
        assert hasattr(result, "sandbox_enforced")
        assert isinstance(result.redactions_input_count, int)
        assert isinstance(result.redactions_output_count, int)
        assert isinstance(result.sandbox_enforced, bool)
