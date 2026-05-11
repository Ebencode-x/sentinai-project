"""Tests for RemediationPipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.models.events import LogIncident, RemediationSuggestion
from src.services.pipeline import PipelineResult, RemediationPipeline


def _incident(incident_id: str = "abc123") -> LogIncident:
    return LogIncident(
        incident_id=incident_id,
        detected_at_utc=datetime.now(UTC),
        severity="critical",
        trigger_line="KeyError: user_id",
        stacktrace="Traceback: File app.py line 42",
        context_before_error="",
    )


def _suggestion(
    patch: str | None = None,
    patch_file: str | None = None,
) -> RemediationSuggestion:
    return RemediationSuggestion(
        summary="Fix KeyError",
        proposed_code_fix="Add .get()",
        proposed_config_change="None",
        confidence=0.8,
        risks="Low",
        source="stub",
        proposed_patch=patch,
        patch_file=patch_file,
    )


def _make_pipeline(
    suggestion: RemediationSuggestion,
    project_root: Path | None = None,
    dry_run: bool = True,
) -> RemediationPipeline:
    kwargs: dict = {"dry_run": dry_run}
    if project_root is not None:
        kwargs["project_root"] = project_root
    with (
        patch("src.services.pipeline.GitHubClient"),
        patch("src.services.pipeline.build_llm_client"),
    ):
        p = RemediationPipeline(**kwargs)
    p._engine = MagicMock()
    p._engine.suggest_fix.return_value = suggestion
    return p


# ---------------------------------------------------------------------------
# No-patch path
# ---------------------------------------------------------------------------


class TestPipelineNoPatch:
    def test_returns_suggestion_only_when_no_patch(self) -> None:
        pipeline = _make_pipeline(_suggestion())
        result = pipeline.run(_incident())
        assert isinstance(result, PipelineResult)
        assert result.suggestion.summary == "Fix KeyError"
        assert result.patch_applied is False
        assert result.tests_passed is None
        assert result.pr_url is None

    def test_llm_failure_sets_failure_reason(self) -> None:
        pipeline = _make_pipeline(_suggestion())
        pipeline._engine.suggest_fix.side_effect = RuntimeError("LLM down")
        result = pipeline.run(_incident())
        assert result.failure_reason is not None
        assert "LLM stage failed" in result.failure_reason


# ---------------------------------------------------------------------------
# Patch apply failures
# ---------------------------------------------------------------------------


class TestPipelinePatchFailures:
    def test_missing_source_file_sets_failure(self, tmp_path: Path) -> None:
        diff = "--- a/nonexistent.py\n+++ b/nonexistent.py\n"
        sug = _suggestion(patch=diff, patch_file="nonexistent.py")
        pipeline = _make_pipeline(sug, project_root=tmp_path)
        result = pipeline.run(_incident())
        assert result.patch_applied is False
        assert result.failure_reason is not None

    def test_invalid_diff_sets_failure(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
        sug = _suggestion(patch="not a valid diff", patch_file="app.py")
        pipeline = _make_pipeline(sug, project_root=tmp_path)
        result = pipeline.run(_incident())
        assert result.patch_applied is False


# ---------------------------------------------------------------------------
# PatchRunner unit tests
# ---------------------------------------------------------------------------


class TestPatchRunner:
    def test_apply_missing_file(self, tmp_path: Path) -> None:
        from src.services.patch_runner import PatchRunner

        runner = PatchRunner(project_root=tmp_path)
        diff = "--- a/x.py\n+++ b/x.py\n"
        r = runner.apply(diff, "x.py", tmp_path / "ws")
        assert not r.success
        assert "not found" in r.error

    def test_apply_invalid_diff(self, tmp_path: Path) -> None:
        from src.services.patch_runner import PatchRunner

        (tmp_path / "x.py").write_text("a = 1\n", encoding="utf-8")
        runner = PatchRunner(project_root=tmp_path)
        r = runner.apply("garbage", "x.py", tmp_path / "ws")
        assert not r.success

    def test_apply_no_change(self, tmp_path: Path) -> None:
        from src.services.patch_runner import PatchRunner

        (tmp_path / "x.py").write_text("a = 1\n", encoding="utf-8")
        runner = PatchRunner(project_root=tmp_path)
        diff = "--- a/x.py\n+++ b/x.py\n@@ -1,1 +1,1 @@\n a = 1\n"
        r = runner.apply(diff, "x.py", tmp_path / "ws")
        assert not r.success
        assert "no changes" in r.error

    def test_apply_valid_patch(self, tmp_path: Path) -> None:
        from src.services.patch_runner import PatchRunner

        (tmp_path / "x.py").write_text("a = 1\n", encoding="utf-8")
        runner = PatchRunner(project_root=tmp_path)
        diff = "--- a/x.py\n+++ b/x.py\n@@ -1,1 +1,1 @@\n-a = 1\n+a = 2\n"
        ws = tmp_path / "ws"
        r = runner.apply(diff, "x.py", ws)
        assert r.success
        assert (ws / "x.py").read_text(encoding="utf-8") == "a = 2\n"

    def test_run_tests_returns_test_result(self, tmp_path: Path) -> None:
        from src.services.patch_runner import PatchRunner, TestResult

        runner = PatchRunner(project_root=tmp_path)
        result = runner.run_tests(workspace=tmp_path)
        assert isinstance(result, TestResult)
        assert isinstance(result.success, bool)
        assert isinstance(result.output, str)
