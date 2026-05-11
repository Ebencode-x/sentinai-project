"""Tests for pipeline policy gate integration — A2/A3."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from src.models.events import LogIncident, RemediationSuggestion
from src.services.pipeline import RemediationPipeline


def _incident() -> LogIncident:
    return LogIncident(
        incident_id="test-001",
        detected_at_utc=datetime.now(UTC),
        severity="critical",
        trigger_line="KeyError: user_id",
        stacktrace="Traceback: File app.py line 42",
        context_before_error="",
    )


def _suggestion(patch: str, patch_file: str) -> RemediationSuggestion:
    return RemediationSuggestion(
        summary="Fix",
        proposed_code_fix="fix",
        proposed_config_change="none",
        confidence=0.8,
        risks="low",
        source="stub",
        proposed_patch=patch,
        patch_file=patch_file,
    )


@pytest.fixture()
def policy_file(tmp_path: Path) -> Path:
    policy = {
        "allowed_paths": ["src/", "tests/"],
        "blocked_paths": [".env", ".github/"],
        "max_files_changed": 5,
        "max_patch_lines": 120,
        "forbidden_patterns": ["shell=True", "eval("],
        "require_tests_pass": True,
        "risk_tiers": {
            "high": {"block": True, "patterns": ["auth", "secret"]},
            "medium": {"require_human_review": True, "patterns": ["src/services/"]},
            "low": {"auto_pr": True, "patterns": ["tests/"]},
        },
    }
    p = tmp_path / "policy.yml"
    p.write_text(yaml.dump(policy), encoding="utf-8")
    return p


def _make_pipeline(
    suggestion: RemediationSuggestion,
    policy_file: Path,
    project_root: Path,
) -> RemediationPipeline:
    with (
        patch("src.services.pipeline.GitHubClient"),
        patch("src.services.pipeline.build_llm_client"),
    ):
        p = RemediationPipeline(
            project_root=project_root,
            dry_run=True,
            policy_path=policy_file,
        )
    p._engine = MagicMock()
    p._engine.suggest_fix.return_value = suggestion
    return p


class TestPolicyGateInPipeline:
    def test_blocked_path_stops_pipeline(self, tmp_path: Path, policy_file: Path) -> None:
        sug = _suggestion("- old\n+ new\n", ".env")
        pipeline = _make_pipeline(sug, policy_file, tmp_path)
        result = pipeline.run(_incident())
        assert result.policy_decision == "block"
        assert result.patch_applied is False
        assert "Policy BLOCK" in (result.failure_reason or "")

    def test_forbidden_pattern_stops_pipeline(self, tmp_path: Path, policy_file: Path) -> None:
        sug = _suggestion("+    subprocess.run(cmd, shell=True)\n", "src/x.py")
        pipeline = _make_pipeline(sug, policy_file, tmp_path)
        result = pipeline.run(_incident())
        assert result.policy_decision == "block"
        assert result.patch_applied is False

    def test_medium_risk_requires_review(self, tmp_path: Path, policy_file: Path) -> None:
        sug = _suggestion("- old\n+ new\n", "src/services/watcher.py")
        pipeline = _make_pipeline(sug, policy_file, tmp_path)
        result = pipeline.run(_incident())
        assert result.policy_decision == "review"
        assert result.patch_applied is False
        assert "REVIEW" in (result.failure_reason or "")

    def test_high_risk_auth_blocked(self, tmp_path: Path, policy_file: Path) -> None:
        sug = _suggestion("- old\n+ new\n", "src/api/auth.py")
        pipeline = _make_pipeline(sug, policy_file, tmp_path)
        result = pipeline.run(_incident())
        assert result.policy_decision == "block"
        assert result.risk_tier == "high"

    def test_low_risk_test_file_proceeds(self, tmp_path: Path, policy_file: Path) -> None:
        # patch_file allowed but source doesn't exist → patch apply fails
        # but policy gate passes (decision=allow)
        sug = _suggestion("- old\n+ new\n", "tests/test_x.py")
        pipeline = _make_pipeline(sug, policy_file, tmp_path)
        result = pipeline.run(_incident())
        assert result.policy_decision == "allow"
        assert result.risk_tier == "low"

    def test_policy_decision_stored_on_result(self, tmp_path: Path, policy_file: Path) -> None:
        sug = _suggestion("- old\n+ new\n", ".env")
        pipeline = _make_pipeline(sug, policy_file, tmp_path)
        result = pipeline.run(_incident())
        assert result.policy_decision is not None
        assert result.risk_tier is not None
