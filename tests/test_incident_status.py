from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.api import routes
from src.models.events import LogIncident

ADMIN = SimpleNamespace(email="admin@sentinai.local")
SEEN = datetime(2026, 11, 5, 12, 0, 0, tzinfo=UTC)


def _incident(**extra) -> LogIncident:
    return LogIncident(
        incident_id="fp-1",
        detected_at_utc=SEEN,
        trigger_line="RuntimeError: wiring test",
        stacktrace="trace",
        source="agrolink",
        **extra,
    )


def test_a_new_incident_is_open_by_default():
    incident = _incident()
    assert incident.status == "open"
    assert incident.resolved_at is None
    assert incident.resolved_by is None


def test_incidents_route_reports_the_real_status(monkeypatch):
    resolved = _incident(status="resolved", resolved_at=SEEN, resolved_by="admin@sentinai.local")
    monkeypatch.setattr(routes.app_state, "incidents", lambda: [resolved])
    item = routes.incidents()[0]
    assert item["status"] == "resolved"
    assert item["resolved_at"] == SEEN.isoformat()
    assert item["resolved_by"] == "admin@sentinai.local"


def test_resolve_route_passes_the_admin_email_to_the_state(monkeypatch):
    calls = []
    monkeypatch.setattr(
        routes.app_state,
        "set_incident_status",
        lambda incident_id, status, email: calls.append((incident_id, status, email)) or True,
    )
    result = routes.resolve_incident("fp-1", user=ADMIN)
    assert result == {"id": "fp-1", "status": "resolved"}
    assert calls == [("fp-1", "resolved", "admin@sentinai.local")]


def test_reopen_route_sets_the_status_back_to_open(monkeypatch):
    calls = []
    monkeypatch.setattr(
        routes.app_state,
        "set_incident_status",
        lambda incident_id, status, email: calls.append((incident_id, status, email)) or True,
    )
    result = routes.reopen_incident("fp-1", user=ADMIN)
    assert result == {"id": "fp-1", "status": "open"}
    assert calls == [("fp-1", "open", "admin@sentinai.local")]


def test_an_unknown_incident_gives_404(monkeypatch):
    monkeypatch.setattr(routes.app_state, "set_incident_status", lambda *args: False)
    with pytest.raises(HTTPException) as caught:
        routes.resolve_incident("missing", user=ADMIN)
    assert caught.value.status_code == 404
