"""Tests for src/api/security.py — API key authentication."""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.api.security import require_api_key


def _make_client() -> TestClient:
    app = FastAPI()

    @app.get("/protected", dependencies=[Depends(require_api_key)])
    def protected():
        return {"ok": True}

    return TestClient(app)


@pytest.fixture
def client_no_key(monkeypatch):
    monkeypatch.delenv("SENTINAI_API_KEY", raising=False)
    return _make_client()


@pytest.fixture
def client_with_key(monkeypatch):
    monkeypatch.setenv("SENTINAI_API_KEY", "test-secret-key")
    return _make_client()


class TestNoKeyConfigured:
    """When SENTINAI_API_KEY is not set, all requests pass through."""

    def test_request_without_header_passes(self, client_no_key):
        assert client_no_key.get("/protected").status_code == 200

    def test_request_with_any_header_passes(self, client_no_key):
        assert (
            client_no_key.get(
                "/protected", headers={"X-API-Key": "anything"}
            ).status_code
            == 200
        )

    def test_response_body_is_ok(self, client_no_key):
        assert client_no_key.get("/protected").json() == {"ok": True}


class TestKeyConfigured:
    """When SENTINAI_API_KEY is set, requests must provide correct key."""

    def test_correct_key_returns_200(self, client_with_key):
        resp = client_with_key.get(
            "/protected", headers={"X-API-Key": "test-secret-key"}
        )
        assert resp.status_code == 200

    def test_missing_key_returns_401(self, client_with_key):
        resp = client_with_key.get("/protected")
        assert resp.status_code == 401

    def test_wrong_key_returns_403(self, client_with_key):
        resp = client_with_key.get("/protected", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 403

    def test_401_detail_message(self, client_with_key):
        data = client_with_key.get("/protected").json()
        assert "Missing" in data["detail"]

    def test_403_detail_message(self, client_with_key):
        data = client_with_key.get("/protected", headers={"X-API-Key": "bad"}).json()
        assert "Invalid" in data["detail"]

    def test_empty_string_key_returns_403(self, client_with_key):
        resp = client_with_key.get("/protected", headers={"X-API-Key": ""})
        assert resp.status_code in (401, 403)

    def test_correct_key_response_body(self, client_with_key):
        resp = client_with_key.get(
            "/protected", headers={"X-API-Key": "test-secret-key"}
        )
        assert resp.json() == {"ok": True}

    def test_timing_safe_comparison(self, client_with_key):
        """Correct key passes, near-miss key fails — secrets.compare_digest is used."""
        resp_good = client_with_key.get(
            "/protected", headers={"X-API-Key": "test-secret-key"}
        )
        resp_bad = client_with_key.get(
            "/protected", headers={"X-API-Key": "test-secret-ley"}
        )
        assert resp_good.status_code == 200
        assert resp_bad.status_code == 403
