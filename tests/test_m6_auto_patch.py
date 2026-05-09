"""Tests for Milestone 6 -- auto-patch PR workflow and Slack PR link.

Coverage:
- GitHubClient.open_patch_pr: success path, branch-already-exists (422), GitHub error
- _build_slack_payload: PR link block present when pr_url set, absent when not
- RemediationEngine.suggest_fix: PR opened + Slack notified, PR skipped when no
  proposed_patch, Slack failure does not propagate
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from github import GithubException

from src.integrations.github_client import GitHubClient
from src.integrations.notifier import _build_slack_payload
from src.models.events import LogIncident, RemediationSuggestion
from src.services.remediation_engine import RemediationEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_incident() -> LogIncident:
    return LogIncident(
        incident_id="abcdef12-0000-0000-0000-000000000000",
        detected_at_utc=datetime(2026, 5, 9, 10, 0, 0, tzinfo=timezone.utc),
        severity="critical",
        trigger_line="ERROR division by zero in compute()",
        stacktrace="Traceback:\n  File main.py line 7\nZeroDivisionError: division by zero",
        context_before_error="INFO starting compute()",
    )


def _make_suggestion(pr_url: str | None = None, proposed_patch: str | None = "x = 1") -> RemediationSuggestion:
    return RemediationSuggestion(
        summary="Divide-by-zero in compute().",
        proposed_code_fix="Guard divisor with if check.",
        proposed_config_change="",
        confidence=0.80,
        risks="Ensure logic is not bypassed.",
        source="provider",
        proposed_patch=proposed_patch,
        test_guidance="Assert ZeroDivisionError is not raised.",
        pr_url=pr_url,
    )


def _mock_github_client(pr_url: str = "https://github.com/org/repo/pull/42") -> MagicMock:
    """Return a GitHubClient with all PyGithub internals mocked."""
    mock_repo = MagicMock()
    mock_repo.default_branch = "main"
    mock_branch = MagicMock()
    mock_branch.commit.sha = "deadbeef"
    mock_repo.get_branch.return_value = mock_branch
    mock_repo.create_git_ref.return_value = MagicMock()

    mock_pr = MagicMock()
    mock_pr.number = 42
    mock_pr.html_url = pr_url
    mock_repo.create_pull.return_value = mock_pr

    with patch("src.integrations.github_client.Github") as mock_gh_cls, \
         patch("src.integrations.github_client.settings") as mock_settings:
        mock_settings.github_token = "tok"
        mock_settings.github_repo = "org/repo"
        mock_gh_cls.return_value.get_repo.return_value = mock_repo
        client = GitHubClient()
        client._repo = mock_repo
    return client


# ---------------------------------------------------------------------------
# GitHubClient -- open_patch_pr success
# ---------------------------------------------------------------------------

def test_open_patch_pr_returns_pr_url() -> None:
    client = _mock_github_client()
    url = client.open_patch_pr(
        incident_id="abcdef12-xxxx",
        trigger_line="ERROR boom",
        summary="Something broke.",
        proposed_patch="fix = True",
        test_guidance="Assert fix is True.",
        confidence=0.9,
    )
    assert url == "https://github.com/org/repo/pull/42"


def test_open_patch_pr_creates_branch_with_correct_prefix() -> None:
    client = _mock_github_client()
    client.open_patch_pr(
        incident_id="abcdef12-xxxx",
        trigger_line="ERROR boom",
        summary="Summary.",
        proposed_patch="fix = True",
        test_guidance="",
        confidence=0.75,
    )
    call_args = client._repo.create_git_ref.call_args
    ref = call_args[1]["ref"] if call_args[1] else call_args[0][0]
    assert ref.startswith("refs/heads/sentinai/fix-")


def test_open_patch_pr_branch_already_exists_still_opens_pr() -> None:
    client = _mock_github_client()
    exc = GithubException(422, {"message": "Reference already exists"}, {})
    client._repo.create_git_ref.side_effect = exc
    url = client.open_patch_pr(
        incident_id="abcdef12-xxxx",
        trigger_line="ERROR boom",
        summary="Summary.",
        proposed_patch="fix = True",
        test_guidance="",
        confidence=0.75,
    )
    assert url == "https://github.com/org/repo/pull/42"


def test_open_patch_pr_returns_none_on_branch_creation_error() -> None:
    client = _mock_github_client()
    exc = GithubException(500, {"message": "Server error"}, {})
    client._repo.create_git_ref.side_effect = exc
    url = client.open_patch_pr(
        incident_id="abcdef12-xxxx",
        trigger_line="ERROR boom",
        summary="Summary.",
        proposed_patch="fix = True",
        test_guidance="",
        confidence=0.75,
    )
    assert url is None


def test_open_patch_pr_returns_none_on_pr_creation_error() -> None:
    client = _mock_github_client()
    client._repo.create_pull.side_effect = GithubException(422, {"message": "PR already exists"}, {})
    url = client.open_patch_pr(
        incident_id="abcdef12-xxxx",
        trigger_line="ERROR boom",
        summary="Summary.",
        proposed_patch="fix = True",
        test_guidance="",
        confidence=0.75,
    )
    assert url is None


# ---------------------------------------------------------------------------
# Slack payload -- PR link block
# ---------------------------------------------------------------------------

def test_slack_payload_includes_pr_link_when_pr_url_set() -> None:
    suggestion = _make_suggestion(pr_url="https://github.com/org/repo/pull/42")
    payload = _build_slack_payload(_make_incident(), suggestion)
    assert "https://github.com/org/repo/pull/42" in str(payload)
    assert "Auto-Patch PR" in str(payload)


def test_slack_payload_excludes_pr_link_when_pr_url_none() -> None:
    suggestion = _make_suggestion(pr_url=None)
    payload = _build_slack_payload(_make_incident(), suggestion)
    assert "Auto-Patch PR" not in str(payload)


def test_slack_payload_pr_link_is_slack_hyperlink_format() -> None:
    pr_url = "https://github.com/org/repo/pull/99"
    suggestion = _make_suggestion(pr_url=pr_url)
    payload = _build_slack_payload(_make_incident(), suggestion)
    # Slack mrkdwn hyperlink format: <url|label>
    assert f"<{pr_url}|" in str(payload)


# ---------------------------------------------------------------------------
# RemediationEngine -- PR + Slack integration
# ---------------------------------------------------------------------------

def _make_llm_suggestion(proposed_patch: str | None = "fix = True") -> RemediationSuggestion:
    return _make_suggestion(proposed_patch=proposed_patch)


def test_remediation_engine_calls_notify_after_pr_created() -> None:
    incident = _make_incident()
    llm_suggestion = _make_llm_suggestion()

    mock_llm = MagicMock()
    mock_llm.analyze_incident.return_value = llm_suggestion

    with patch("src.services.remediation_engine.settings") as mock_settings, \
         patch("src.services.remediation_engine.GitHubClient") as mock_gh_cls, \
         patch("src.services.remediation_engine.notifier") as mock_notifier:

        mock_settings.github_token = "tok"
        mock_settings.github_repo = "org/repo"

        mock_github = MagicMock()
        mock_github.open_patch_pr.return_value = "https://github.com/org/repo/pull/7"
        mock_gh_cls.return_value = mock_github

        engine = RemediationEngine(llm_client=mock_llm)
        result = engine.suggest_fix(incident)

    mock_notifier.notify.assert_called_once()
    assert result.pr_url == "https://github.com/org/repo/pull/7"


def test_remediation_engine_skips_pr_when_no_proposed_patch() -> None:
    incident = _make_incident()
    llm_suggestion = _make_llm_suggestion(proposed_patch=None)

    mock_llm = MagicMock()
    mock_llm.analyze_incident.return_value = llm_suggestion

    with patch("src.services.remediation_engine.settings") as mock_settings, \
         patch("src.services.remediation_engine.GitHubClient") as mock_gh_cls, \
         patch("src.services.remediation_engine.notifier") as mock_notifier:

        mock_settings.github_token = "tok"
        mock_settings.github_repo = "org/repo"

        mock_github = MagicMock()
        mock_gh_cls.return_value = mock_github

        engine = RemediationEngine(llm_client=mock_llm)
        result = engine.suggest_fix(incident)

    mock_github.open_patch_pr.assert_not_called()
    mock_notifier.notify.assert_not_called()
    assert result.pr_url is None


def test_remediation_engine_skips_notify_when_pr_url_is_none() -> None:
    """GitHub returns None (PR creation failed) -- Slack must not be called."""
    incident = _make_incident()
    llm_suggestion = _make_llm_suggestion()

    mock_llm = MagicMock()
    mock_llm.analyze_incident.return_value = llm_suggestion

    with patch("src.services.remediation_engine.settings") as mock_settings, \
         patch("src.services.remediation_engine.GitHubClient") as mock_gh_cls, \
         patch("src.services.remediation_engine.notifier") as mock_notifier:

        mock_settings.github_token = "tok"
        mock_settings.github_repo = "org/repo"

        mock_github = MagicMock()
        mock_github.open_patch_pr.return_value = None
        mock_gh_cls.return_value = mock_github

        engine = RemediationEngine(llm_client=mock_llm)
        result = engine.suggest_fix(incident)

    mock_notifier.notify.assert_not_called()


def test_remediation_engine_slack_failure_does_not_raise() -> None:
    """Slack throwing must never crash suggest_fix()."""
    incident = _make_incident()
    llm_suggestion = _make_llm_suggestion()

    mock_llm = MagicMock()
    mock_llm.analyze_incident.return_value = llm_suggestion

    with patch("src.services.remediation_engine.settings") as mock_settings, \
         patch("src.services.remediation_engine.GitHubClient") as mock_gh_cls, \
         patch("src.services.remediation_engine.notifier") as mock_notifier:

        mock_settings.github_token = "tok"
        mock_settings.github_repo = "org/repo"

        mock_github = MagicMock()
        mock_github.open_patch_pr.return_value = "https://github.com/org/repo/pull/7"
        mock_gh_cls.return_value = mock_github
        mock_notifier.notify.side_effect = Exception("Slack is down")

        engine = RemediationEngine(llm_client=mock_llm)
        result = engine.suggest_fix(incident)  # must not raise

    assert result is not None
