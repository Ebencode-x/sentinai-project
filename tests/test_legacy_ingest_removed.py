"""The old POST /api/ingest is gone and the v1 route is still mounted."""

from fastapi.testclient import TestClient

from src.main import app


def _paths():
    return {getattr(route, "path", "") for route in app.routes}


def test_the_legacy_ingest_route_is_not_mounted():
    assert not any(path.startswith("/api/ingest") for path in _paths())


def test_the_v1_events_route_still_answers():
    response = TestClient(app, raise_server_exceptions=False).post(
        "/api/v1/events", json={"events": []}
    )
    assert response.status_code in (401, 503)


def test_posting_to_the_legacy_path_is_not_accepted():
    response = TestClient(app).post("/api/ingest", json={"source": "x", "events": []})
    assert response.status_code != 202
