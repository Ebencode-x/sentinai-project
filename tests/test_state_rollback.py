"""The rollback ledger lives in the database, and a patch can only be reverted once."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.core.state import AppState
from src.models.events import LogIncident, RemediationSuggestion


def _broken_factory():
    raise RuntimeError("database down")


def _github(branch_sha="after1", head_sha="after1", merged=True):
    github = MagicMock()
    github.check_pr_merged.return_value = {"merge_commit_sha": "merge1"} if merged else None
    github.get_current_file_sha.side_effect = lambda path, ref=None: branch_sha if ref else head_sha
    github.revert_patch.return_value = "revert1"
    return github


def _state(factory, github) -> AppState:
    state = AppState(session_factory=factory)
    engine = MagicMock()
    engine.github_client = github
    state.remediation_engine = engine
    return state


def _entry(state: AppState) -> dict:
    return state.add_rollback_ledger_entry(
        incident_id="fp-1",
        pr_number=7,
        pr_url="https://example.com/pull/7",
        branch_name="sentinai/fix",
        patch_file="src/x.py",
        before_sha="before1",
    )


def _status(state: AppState, ledger_id: str) -> str:
    return state.get_rollback_ledger_entry(ledger_id)["status"]


def test_an_entry_is_stored_and_survives_a_restart(app_db):
    factory, _ = app_db
    entry = _entry(_state(factory, None))
    assert entry["status"] == "proposed"
    assert entry["incident_id"] == "fp-1"
    reborn = AppState(session_factory=factory)
    assert [e["id"] for e in reborn.list_rollbacks()] == [entry["id"]]


def test_the_list_is_empty_when_nothing_was_recorded(app_db):
    factory, _ = app_db
    assert AppState(session_factory=factory).list_rollbacks() == []


def test_a_database_failure_is_counted_and_does_not_raise():
    state = AppState(session_factory=_broken_factory)
    assert _entry(state) is None
    assert state.persistence_errors == 1


def test_unknown_ids_and_missing_github_are_reported(app_db):
    factory, _ = app_db
    with pytest.raises(ValueError, match="not found"):
        _state(factory, _github()).propose_rollback("nonexistent")
    entry = _entry(_state(factory, None))
    with pytest.raises(ValueError, match="not configured"):
        _state(factory, None).propose_rollback(entry["id"])


def test_an_unmerged_pr_cannot_be_rolled_back(app_db):
    factory, _ = app_db
    state = _state(factory, _github(merged=False))
    entry = _entry(state)
    with pytest.raises(ValueError, match="not been merged"):
        state.propose_rollback(entry["id"])
    assert _status(state, entry["id"]) == "proposed"


def test_a_clean_revert_is_offered_and_the_facts_are_stored(app_db):
    factory, _ = app_db
    state = _state(factory, _github())
    entry = _entry(state)
    result = state.propose_rollback(entry["id"])
    assert result["conflict"] is False
    stored = state.get_rollback_ledger_entry(entry["id"])
    assert stored["status"] == "rollback_proposed"
    assert stored["merge_commit_sha"] == "merge1"
    assert stored["after_sha"] == "after1"
    assert stored["rollback_current_sha"] == "after1"


def test_a_file_changed_since_the_patch_blocks_the_revert(app_db):
    factory, _ = app_db
    state = _state(factory, _github(head_sha="someone-else"))
    entry = _entry(state)
    result = state.propose_rollback(entry["id"])
    assert result["conflict"] is True
    assert _status(state, entry["id"]) == "rollback_blocked"


def test_confirm_needs_a_proposal_first(app_db):
    factory, _ = app_db
    state = _state(factory, _github())
    entry = _entry(state)
    with pytest.raises(ValueError, match="Call propose first"):
        state.confirm_rollback(entry["id"])


def test_confirm_reverts_once_and_stores_the_revert_commit(app_db):
    factory, _ = app_db
    github = _github()
    state = _state(factory, github)
    entry = _entry(state)
    state.propose_rollback(entry["id"])
    result = state.confirm_rollback(entry["id"])
    assert result == {
        "ledger_id": entry["id"],
        "status": "rolled_back",
        "revert_commit_sha": "revert1",
    }
    github.revert_patch.assert_called_once_with(
        patch_file="src/x.py",
        before_sha="before1",
        current_sha="after1",
        incident_id="fp-1",
    )
    assert state.get_rollback_ledger_entry(entry["id"])["revert_commit_sha"] == "revert1"


def test_a_second_confirm_and_a_new_proposal_are_both_refused(app_db):
    factory, _ = app_db
    github = _github()
    state = _state(factory, github)
    entry = _entry(state)
    state.propose_rollback(entry["id"])
    state.confirm_rollback(entry["id"])
    with pytest.raises(ValueError, match="rolled_back"):
        state.confirm_rollback(entry["id"])
    with pytest.raises(ValueError, match="already been rolled back"):
        state.propose_rollback(entry["id"])
    assert github.revert_patch.call_count == 1
    assert _status(state, entry["id"]) == "rolled_back"


def test_a_failed_revert_leaves_the_proposal_in_place(app_db):
    factory, _ = app_db
    github = _github()
    github.revert_patch.return_value = None
    state = _state(factory, github)
    entry = _entry(state)
    state.propose_rollback(entry["id"])
    with pytest.raises(ValueError, match="Revert commit failed"):
        state.confirm_rollback(entry["id"])
    assert _status(state, entry["id"]) == "rollback_proposed"


def test_a_scan_that_opens_a_pr_records_it_in_the_ledger(app_db):
    factory, _ = app_db
    state = _state(factory, _github())
    incident = LogIncident(
        incident_id="fp-scan",
        detected_at_utc=datetime.now(UTC),
        trigger_line="KeyError: 'x'",
        stacktrace="Traceback (most recent call last):",
    )
    suggestion = RemediationSuggestion(
        summary="s",
        proposed_code_fix="c",
        proposed_config_change="x",
        confidence=0.9,
        risks="low",
        pr_number=7,
        pr_url="https://example.com/pull/7",
        patch_file="src/x.py",
        before_sha="before1",
        branch_name="sentinai/fix",
    )
    state.watcher.scan_once = lambda: [incident]
    state._record_audit = lambda inc, sug: None
    state.remediation_engine.suggest_fix.return_value = suggestion
    with patch("src.core.state.notify"):
        state.scan_logs_once()
    entries = state.list_rollbacks()
    assert [e["pr_number"] for e in entries] == [7]
    assert entries[0]["incident_id"] == "fp-scan"
