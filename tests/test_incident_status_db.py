"""Resolving an incident sticks until the error comes back after the resolve time."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from sqlalchemy import select

from src.core.state import AppState
from src.db.models import Incident
from src.models.events import LogIncident, RemediationSuggestion

FP = "fp-status-1"
ADMIN = "admin@sentinai.local"


def _sighting(when: datetime) -> LogIncident:
    return LogIncident(
        incident_id=FP,
        detected_at_utc=when,
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


def _state(factory, sightings) -> AppState:
    state = AppState(session_factory=factory)
    state.watcher.scan_once = lambda: list(sightings)
    state._record_audit = lambda incident, suggestion: None
    engine = MagicMock()
    engine.suggest_fix.return_value = _suggestion()
    state.remediation_engine = engine
    return state


def _stored(factory) -> dict:
    with factory() as db:
        row = db.scalars(select(Incident)).one()
        return {
            "status": row.status,
            "resolved_at": row.resolved_at,
            "resolved_by": row.resolved_by,
            "occurrences": row.occurrence_count,
        }


def test_a_repeat_after_the_resolve_reopens_the_incident(app_db):
    factory, _ = app_db
    sightings = [_sighting(datetime.now(UTC))]
    state = _state(factory, sightings)
    with patch("src.core.state.notify"):
        state.scan_logs_once()
        assert state.set_incident_status(FP, "resolved", ADMIN) is True
        assert _stored(factory)["status"] == "resolved"
        sightings[:] = [_sighting(datetime.now(UTC) + timedelta(hours=1))]
        state.scan_logs_once()
    stored = _stored(factory)
    assert stored["status"] == "open"
    assert stored["resolved_at"] is None
    assert stored["resolved_by"] is None
    assert stored["occurrences"] == 2


def test_a_repeat_from_before_the_resolve_does_not_reopen_it(app_db):
    factory, _ = app_db
    sightings = [_sighting(datetime.now(UTC))]
    state = _state(factory, sightings)
    with patch("src.core.state.notify"):
        state.scan_logs_once()
        state.set_incident_status(FP, "resolved", ADMIN)
        sightings[:] = [_sighting(datetime.now(UTC) - timedelta(hours=1))]
        state.scan_logs_once()
    stored = _stored(factory)
    assert stored["status"] == "resolved"
    assert stored["resolved_by"] == ADMIN
    assert stored["occurrences"] == 2


def test_a_resolved_incident_stays_resolved_after_a_restart(app_db):
    factory, _ = app_db
    state = _state(factory, [_sighting(datetime.now(UTC))])
    with patch("src.core.state.notify"):
        state.scan_logs_once()
    state.set_incident_status(FP, "resolved", ADMIN)
    reborn = AppState(session_factory=factory)
    assert [i.status for i in reborn.incidents()] == ["resolved"]
