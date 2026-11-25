"""PR P: suggest_fix runs the policy before any PR is opened (end to end)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from src.models.events import LogIncident, RemediationSuggestion
from src.services import policy_engine
from src.services.policy_engine import Decision, PatchPolicyEngine, PolicyResult
from src.services.remediation_engine import RemediationEngine

POLICY_YML = """\
allowed_paths:
  - src/
  - tests/
blocked_paths:
  - .github/
  - Dockerfile
forbidden_patterns:
  - "eval("
max_files_changed: 5
max_patch_lines: 120
"""

PR_RESULT = {
    "pr_url": "https://github.com/owner/repo/pull/1",
    "pr_number": 1,
    "patch_file": "src/a.py",
    "before_sha": "abc123",
    "branch_name": "sentinai/fix-1",
}


def _diff(path: str) -> str:
    return f"--- a/{path}\n+++ b/{path}\n@@ -1,2 +1,2 @@\n x = 1\n-y = 2\n+y = 3\n"


def _incident() -> LogIncident:
    return LogIncident(
        incident_id="abcdef12-0000-0000-0000-000000000000",
        detected_at_utc=datetime(2026, 5, 9, 10, 0, 0, tzinfo=UTC),
        severity="critical",
        trigger_line="ERROR division by zero in compute()",
        stacktrace="Traceback:\n  File main.py line 7\nZeroDivisionError: division by zero",
        context_before_error="INFO starting compute()",
    )


class _FixedPolicy:
    def __init__(self, decision: Decision) -> None:
        self.decision = decision

    def check(self, patch: str, patch_file: str, files_changed: int = 1) -> PolicyResult:
        return PolicyResult(decision=self.decision, reasons=("test reason",), risk_tier="medium")


class _AlwaysAllow:
    def consume(self) -> bool:
        return True


def _real_policy(tmp_path: Path) -> PatchPolicyEngine:
    path = tmp_path / "policy.yml"
    path.write_text(POLICY_YML, encoding="utf-8")
    return PatchPolicyEngine(policy_path=path)


@contextmanager
def _live_engine(diff: str, policy: object | None) -> Iterator[tuple[RemediationEngine, MagicMock]]:
    github = MagicMock()
    github.open_patch_pr.return_value = PR_RESULT
    llm = MagicMock()
    suggestion = RemediationSuggestion(
        summary="s",
        proposed_code_fix="c",
        proposed_config_change="",
        confidence=0.9,
        risks="r",
        proposed_patch=diff,
        model="test-model",
    )
    llm.analyze_incident.return_value = suggestion
    with (
        patch("src.services.remediation_engine.settings") as settings,
        patch("src.services.remediation_engine.GitHubClient", return_value=github),
        patch("src.services.remediation_engine.notifier"),
        patch("src.services.remediation_engine.llm_rate_limiter", _AlwaysAllow()),
        patch("src.services.remediation_engine.pr_rate_limiter", _AlwaysAllow()),
    ):
        settings.github_token = "token"
        settings.github_repo = "owner/repo"
        engine = RemediationEngine(llm_client=llm, policy=cast("PatchPolicyEngine | None", policy))
        yield engine, github


def test_auto_pr_never_opens_a_pr_for_a_blocked_path(tmp_path: Path) -> None:
    with _live_engine(_diff(".github/workflows/ci.yml"), _real_policy(tmp_path)) as (eng, gh):
        result = eng.suggest_fix(_incident(), autonomy_mode="auto_pr")
    gh.open_patch_pr.assert_not_called()
    assert result.proposed_patch is None
    assert result.pr_url is None
    assert "blocked path" in (result.provider_error or "")


def test_auto_pr_opens_the_pr_when_the_policy_allows() -> None:
    diff = _diff("src/a.py")
    with _live_engine(diff, _FixedPolicy(Decision.ALLOW)) as (eng, gh):
        result = eng.suggest_fix(_incident(), autonomy_mode="auto_pr")
    gh.open_patch_pr.assert_called_once()
    assert gh.open_patch_pr.call_args.kwargs["proposed_patch"] == diff
    assert result.pr_url == PR_RESULT["pr_url"]


def test_auto_pr_waits_for_approval_when_the_policy_says_review() -> None:
    diff = _diff("src/a.py")
    with _live_engine(diff, _FixedPolicy(Decision.REVIEW)) as (eng, gh):
        result = eng.suggest_fix(_incident(), autonomy_mode="auto_pr")
    gh.open_patch_pr.assert_not_called()
    assert result.awaiting_approval is True
    assert result.proposed_patch == diff
    assert (result.provider_error or "").startswith("Policy REVIEW")


def test_propose_only_does_not_offer_a_blocked_patch(tmp_path: Path) -> None:
    with _live_engine(_diff(".github/workflows/ci.yml"), _real_policy(tmp_path)) as (eng, gh):
        result = eng.suggest_fix(_incident(), autonomy_mode="propose_only")
    gh.open_patch_pr.assert_not_called()
    assert result.proposed_patch is None
    assert result.awaiting_approval is False


def test_auto_pr_fails_closed_when_the_policy_file_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(policy_engine, "_DEFAULT_POLICY", tmp_path / "missing.yml")
    with _live_engine(_diff("src/a.py"), None) as (eng, gh):
        result = eng.suggest_fix(_incident(), autonomy_mode="auto_pr")
    gh.open_patch_pr.assert_not_called()
    assert result.proposed_patch is None
    assert "policy unavailable" in (result.provider_error or "")
