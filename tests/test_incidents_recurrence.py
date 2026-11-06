from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from src.api import routes
from src.db.repository import _to_incident
from src.models.events import LogIncident

FIRST = datetime(2026, 11, 1, 20, 2, 50, tzinfo=UTC)
LATEST = FIRST + timedelta(days=4)


def _incident(**extra) -> LogIncident:
    return LogIncident(
        incident_id="fp-1",
        detected_at_utc=FIRST,
        trigger_line="RuntimeError: wiring test",
        stacktrace="trace",
        source="agrolink",
        **extra,
    )


def test_to_incident_carries_recurrence_fields():
    row = SimpleNamespace(
        fingerprint="fp-1",
        detected_at=FIRST,
        severity="critical",
        trigger_line="RuntimeError: wiring test",
        stacktrace="trace",
        context_before_error="",
        source="agrolink",
        last_seen_at=LATEST,
        occurrence_count=6,
        status="open",
        resolved_at=None,
        resolved_by=None,
    )
    incident = _to_incident(row)
    assert incident.last_seen_at == LATEST
    assert incident.occurrence_count == 6


def test_incidents_route_returns_last_seen_and_occurrences(monkeypatch):
    incident = _incident(last_seen_at=LATEST, occurrence_count=6)
    monkeypatch.setattr(routes.app_state, "incidents", lambda: [incident])
    item = routes.incidents()[0]
    assert item["occurrences"] == 6
    assert item["last_seen"] == LATEST.isoformat()
    assert item["timestamp"] == FIRST.isoformat()


def test_incidents_route_defaults_for_a_single_sighting(monkeypatch):
    incident = _incident()
    monkeypatch.setattr(routes.app_state, "incidents", lambda: [incident])
    item = routes.incidents()[0]
    assert item["occurrences"] == 1
    assert item["last_seen"] == FIRST.isoformat()
