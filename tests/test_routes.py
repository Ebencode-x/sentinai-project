"""M8 tests for src/api/routes.py."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.models.events import LogIncident, RemediationSuggestion


def make_incident(incident_id="abc123"):
    return LogIncident(
        incident_id=incident_id,
        detected_at_utc=datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC),
        severity="critical",
        trigger_line="ERROR test failure",
        stacktrace="ERROR test failure",
        context_before_error="INFO warm up",
    )


def make_suggestion(summary="Fix it", source="stub"):
    return RemediationSuggestion(
        summary=summary,
        proposed_code_fix="try: ... except: pass",
        proposed_config_change="LOG_LEVEL=INFO",
        confidence=0.85,
        risks="May swallow errors",
        source=source,
    )


@pytest.fixture
def client():
    from src.api.auth import RateLimitTier, Tenant, require_tenant
    from src.api.security import require_api_key

    async def mock_tenant():
        return Tenant(name="test", tier=RateLimitTier.INTERNAL)

    app.dependency_overrides[require_tenant] = mock_tenant
    app.dependency_overrides[require_api_key] = mock_tenant
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


class TestHealth:
    def test_returns_200(self, client):
        assert client.get("/health").status_code == 200

    def test_status_ok(self, client):
        assert client.get("/health").json()["status"] == "ok"

    def test_service_name(self, client):
        assert client.get("/health").json()["service"] == "sentinai"


class TestStats:
    def test_returns_200(self, client):
        assert client.get("/stats").status_code == 200

    def test_has_service_key(self, client):
        assert "service" in client.get("/stats").json()

    def test_has_llm_metrics(self, client):
        assert "llm_metrics" in client.get("/stats").json()

    def test_has_buffer_count(self, client):
        assert "buffer_incident_count" in client.get("/stats").json()


class TestPrometheusMetrics:
    def test_returns_200(self, client):
        assert client.get("/metrics").status_code == 200

    def test_content_type_text(self, client):
        assert "text/plain" in client.get("/metrics").headers["content-type"]

    def test_body_is_string(self, client):
        assert isinstance(client.get("/metrics").text, str)


class TestIncidents:
    def test_returns_200(self, client):
        assert client.get("/incidents").status_code == 200

    def test_returns_list(self, client):
        assert isinstance(client.get("/incidents").json(), list)

    def test_incident_appears_in_response(self, client):
        from src.core.state import app_state

        inc = make_incident("route-test-001")
        app_state.recent_incidents.append(inc)
        ids = [i["id"] for i in client.get("/incidents").json()]
        assert "route-test-001" in ids
        app_state.recent_incidents.remove(inc)

    def test_incident_fields_present(self, client):
        from src.core.state import app_state

        inc = make_incident("field-check-002")
        app_state.recent_incidents.append(inc)
        data = client.get("/incidents").json()
        match = next(i for i in data if i["id"] == "field-check-002")
        assert "title" in match
        assert "severity" in match
        app_state.recent_incidents.remove(inc)


class TestSuggestions:
    def test_returns_200(self, client):
        assert client.get("/suggestions").status_code == 200

    def test_returns_list(self, client):
        assert isinstance(client.get("/suggestions").json(), list)

    def test_suggestion_appears_in_response(self, client):
        from src.core.state import app_state

        s = make_suggestion("My specific fix")
        app_state.recent_suggestions.append(s)
        data = client.get("/suggestions").json()
        summaries = [i["summary"] for i in data]
        assert "My specific fix" in summaries
        app_state.recent_suggestions.remove(s)

    def test_suggestion_fields_present(self, client):
        from src.core.state import app_state

        s = make_suggestion()
        app_state.recent_suggestions.append(s)
        last = client.get("/suggestions").json()[-1]
        assert "summary" in last
        assert "confidence" in last
        assert "source" in last
        app_state.recent_suggestions.remove(s)


class TestSuggestionsLatest:
    def test_404_when_empty(self, client):
        from src.core.state import app_state

        app_state.recent_suggestions.clear()
        assert client.get("/suggestions/latest").status_code == 404

    def test_404_detail_message(self, client):
        from src.core.state import app_state

        app_state.recent_suggestions.clear()
        data = client.get("/suggestions/latest").json()
        assert "No suggestions yet" in data["detail"]

    def test_200_when_suggestions_exist(self, client):
        from src.core.state import app_state

        app_state.recent_suggestions.append(make_suggestion())
        assert client.get("/suggestions/latest").status_code == 200
        app_state.recent_suggestions.clear()

    def test_returns_last_suggestion(self, client):
        from src.core.state import app_state

        app_state.recent_suggestions.append(make_suggestion("First"))
        app_state.recent_suggestions.append(make_suggestion("Second"))
        data = client.get("/suggestions/latest").json()
        assert data["summary"] == "Second"
        app_state.recent_suggestions.clear()


class TestScanNow:
    def test_returns_200(self, client):
        assert client.post("/scan-now").status_code == 200

    def test_returns_detected_incidents_key(self, client):
        assert "detected_incidents" in client.post("/scan-now").json()

    def test_detected_incidents_is_int(self, client):
        assert isinstance(client.post("/scan-now").json()["detected_incidents"], int)

    def test_scan_with_mock_returns_correct_count(self, client):
        with patch("src.api.routes.app_state.scan_logs_once", return_value=5) as m:
            data = client.post("/scan-now").json()
            assert data["detected_incidents"] == 5
            m.assert_called_once()
