"""AppState keeps incidents and suggestions in the database, so they survive a restart."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from sqlalchemy import select

from src.core.state import AppState
from src.db.models import Incident
from src.models.events import LogIncident, RemediationSuggestion


def _incident(fingerprint: str = "fp-state-1") -> LogIncident:
    return LogIncident(
        incident_id=fingerprint,
        detected_at_utc=datetime.now(UTC),
        trigger_line="KeyError: 'customer_id'",
        stacktrace="Traceback (most recent call last):",
    )


def _suggestion() -> RemediationSuggestion:
    return RemediationSuggestion(
        summary="Guard the lookup",
        proposed_code_fix="use dict.get",
        proposed_config_change="none",
        confidence=0.8,
        risks="low",
    )


def _broken_factory():
    raise RuntimeError("database down")


def _state(factory, incidents) -> tuple[AppState, MagicMock]:
    state = AppState(session_factory=factory)
    state.watcher.scan_once = lambda: list(incidents)
    state._record_audit = lambda incident, suggestion: None
    engine = MagicMock()
    engine.suggest_fix.return_value = _suggestion()
    state.remediation_engine = engine
    return state, engine


def test_a_scan_stores_the_incident_and_its_suggestion(app_db):
    factory, _ = app_db
    state, _engine = _state(factory, [_incident()])
    with patch("src.core.state.notify"):
        assert state.scan_logs_once() == 1
    assert [i.incident_id for i in state.incidents()] == ["fp-state-1"]
    assert [s.summary for s in state.suggestions()] == ["Guard the lookup"]


def test_data_survives_a_restart(app_db):
    factory, _ = app_db
    first, _engine = _state(factory, [_incident()])
    with patch("src.core.state.notify"):
        first.scan_logs_once()
    reborn = AppState(session_factory=factory)
    assert len(reborn.incidents()) == 1
    assert reborn.latest_suggestion() is not None


def test_a_repeated_error_is_counted_and_the_model_is_not_called_again(app_db):
    factory, _ = app_db
    state, engine = _state(factory, [_incident()])
    with patch("src.core.state.notify") as notify:
        assert state.scan_logs_once() == 1
        assert state.scan_logs_once() == 0
    assert engine.suggest_fix.call_count == 1
    assert notify.call_count == 1
    with factory() as db:
        assert db.scalars(select(Incident)).one().occurrence_count == 2


def test_a_database_failure_does_not_silence_the_alert():
    state, engine = _state(_broken_factory, [_incident()])
    with patch("src.core.state.notify") as notify:
        assert state.scan_logs_once() == 1
    notify.assert_called_once()
    assert engine.suggest_fix.call_count == 1
    assert state.persistence_errors == 1


def test_stats_still_answer_when_the_database_is_down():
    stats = AppState(session_factory=_broken_factory).stats_snapshot()
    assert stats["database_reachable"] is False
    assert stats["buffer_incident_count"] == 0


def test_stats_count_what_is_stored(app_db):
    factory, _ = app_db
    state, _engine = _state(factory, [_incident()])
    with patch("src.core.state.notify"):
        state.scan_logs_once()
    stats = state.stats_snapshot()
    assert stats["database_reachable"] is True
    assert stats["buffer_incident_count"] == 1
    assert stats["buffer_suggestion_count"] == 1
    assert stats["recent_suggestions_by_source"]["stub"] == 1
