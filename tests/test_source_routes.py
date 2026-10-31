"""Admin routes for event sources: keys are shown once and scoped to the admin's account."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.deps import require_user
from src.api.routes import require_admin
from src.api.source_routes import router
from src.core.api_keys import prefix_of
from src.db import sources
from src.db.models import Account, Role
from src.db.session import get_db


@pytest.fixture
def env(app_db):
    factory, account_id = app_db

    def admin():
        return SimpleNamespace(email="admin@test", role=Role.ADMIN, account_id=account_id)

    def session():
        with factory() as db:
            yield db

    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[require_user] = admin
    app.dependency_overrides[require_admin] = admin
    app.dependency_overrides[get_db] = session
    return TestClient(app), factory


def _create(client: TestClient, name: str = "agrolink") -> dict:
    response = client.post("/api/sources", json={"name": name})
    assert response.status_code == 201
    return response.json()


def test_the_list_starts_empty(env):
    client, _ = env
    assert client.get("/api/sources").json() == []


def test_creating_a_source_returns_its_key_once_and_the_list_never_does(env):
    client, factory = env
    created = client.post("/api/sources", json={"name": "agrolink"})
    body = created.json()
    assert created.status_code == 201
    assert created.headers["cache-control"] == "no-store"
    assert body["status"] == "active"
    assert prefix_of(body["key"]) == body["key_prefix"]
    with factory() as db:
        assert sources.authenticate(db, body["key"]) is not None
    listed = client.get("/api/sources")
    assert body["key"] not in listed.text
    assert "key_hash" not in listed.text
    assert "key" not in listed.json()[0]


@pytest.mark.parametrize("bad", ["", "Has Space", "UPPER", "-lead", "x" * 33, "a/b"])
def test_invalid_names_are_rejected(env, bad):
    client, _ = env
    assert client.post("/api/sources", json={"name": bad}).status_code == 422


def test_a_duplicate_name_is_a_conflict(env):
    client, _ = env
    _create(client)
    assert client.post("/api/sources", json={"name": "agrolink"}).status_code == 409


def test_rotating_replaces_the_key_and_shows_the_new_one_once(env):
    client, factory = env
    created = _create(client)
    rotated = client.post(f"/api/sources/{created['id']}/rotate")
    assert rotated.status_code == 200
    assert rotated.headers["cache-control"] == "no-store"
    new_key = rotated.json()["key"]
    assert new_key != created["key"]
    with factory() as db:
        assert sources.authenticate(db, created["key"]) is None
        assert sources.authenticate(db, new_key) is not None
    assert "key" not in client.get("/api/sources").json()[0]


def test_rotating_an_unknown_or_revoked_source_is_refused(env):
    client, _ = env
    assert client.post("/api/sources/nonexistent/rotate").status_code == 404
    created = _create(client)
    client.delete(f"/api/sources/{created['id']}")
    assert client.post(f"/api/sources/{created['id']}/rotate").status_code == 409


def test_revoking_stops_the_key_and_can_be_repeated(env):
    client, factory = env
    created = _create(client)
    source_id = created["id"]
    first = client.delete(f"/api/sources/{source_id}")
    assert first.status_code == 200
    assert first.json() == {"revoked": True, "id": source_id}
    assert client.delete(f"/api/sources/{source_id}").status_code == 200
    with factory() as db:
        assert sources.authenticate(db, created["key"]) is None
    listed = client.get("/api/sources").json()
    assert listed[0]["status"] == "revoked"
    assert listed[0]["revoked_at"] is not None
    assert client.delete("/api/sources/nonexistent").status_code == 404


def test_an_admin_only_sees_and_changes_their_own_accounts_sources(env):
    client, factory = env
    with factory() as db:
        other = Account(name="other")
        db.add(other)
        db.commit()
        foreign, _key = sources.create_source(db, other.id, "foreign")
        foreign_id, other_id = foreign.id, other.id
    assert client.get("/api/sources").json() == []
    assert client.post(f"/api/sources/{foreign_id}/rotate").status_code == 404
    assert client.delete(f"/api/sources/{foreign_id}").status_code == 404
    with factory() as db:
        assert sources.get_source(db, other_id, foreign_id).revoked_at is None


def test_every_route_requires_an_admin():
    assert router.routes
    for route in router.routes:
        assert any(dep.dependency is require_admin for dep in route.dependencies), route.path


def test_the_routes_are_mounted_in_the_app_and_refuse_anonymous_callers():
    from src.main import app

    client = TestClient(app)
    calls = (
        ("GET", "/api/sources", None),
        ("POST", "/api/sources", {"name": "agrolink"}),
        ("POST", "/api/sources/some-id/rotate", None),
        ("DELETE", "/api/sources/some-id", None),
    )
    for method, path, body in calls:
        response = client.request(method, path, json=body)
        # 404 would mean the route is not mounted; 401 or 403 means it is, and protected.
        assert response.status_code in (401, 403), (method, path, response.status_code)
