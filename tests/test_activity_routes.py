"""GET /api/activity/daily returns the signed-in account's counts, and only its own."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.activity_routes import router
from src.api.deps import require_user
from src.db import sources
from src.db.models import Account, IngestedEvent
from src.db.session import get_db


@pytest.fixture
def env(app_db):
    factory, account_id = app_db

    def user():
        return SimpleNamespace(email="viewer@test", role="viewer", account_id=account_id)

    def session():
        with factory() as db:
            yield db

    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[require_user] = user
    app.dependency_overrides[get_db] = session
    return TestClient(app), factory, account_id


def _event(db, account_id, source_id, name):
    now = datetime.now(UTC)
    db.add(
        IngestedEvent(
            account_id=account_id,
            source_id=source_id,
            event_id=name,
            occurred_at=now,
            received_at=now,
            message="boom",
            fingerprint=f"fp-{name}",
        )
    )


def test_a_signed_in_user_gets_the_days_totals_and_sources(env):
    client, factory, account_id = env
    with factory() as db:
        row, _key = sources.create_source(db, account_id, "agrolink")
        _event(db, account_id, row.id, "a")
        _event(db, account_id, row.id, "b")
        db.commit()
    response = client.get("/api/activity/daily", params={"days": 7})
    body = response.json()
    assert response.status_code == 200
    assert body["days"] == 7
    assert len(body["daily"]) == 7
    assert body["totals"]["events"] == 2
    assert [s["name"] for s in body["sources"]] == ["agrolink"]
    assert "key_hash" not in body["sources"][0]
    assert "key_prefix" not in body["sources"][0]


def test_the_default_window_is_six_months(env):
    client, _factory, _account = env
    body = client.get("/api/activity/daily").json()
    assert body["days"] == 182
    assert len(body["daily"]) == 182


def test_another_accounts_activity_is_not_returned(env):
    client, factory, _account = env
    with factory() as db:
        other = Account(name="other")
        db.add(other)
        db.commit()
        other_id = other.id
        row, _key = sources.create_source(db, other_id, "other-app")
        _event(db, other_id, row.id, "x")
        db.commit()
    body = client.get("/api/activity/daily", params={"days": 7}).json()
    assert body["totals"]["events"] == 0
    assert body["sources"] == []


@pytest.mark.parametrize("days", [0, 367, -5])
def test_days_outside_the_range_are_rejected(env, days):
    client, _factory, _account = env
    assert client.get("/api/activity/daily", params={"days": days}).status_code == 422


def test_the_route_is_registered_on_the_real_app():
    from src.main import app

    assert "/api/activity/daily" in app.openapi()["paths"]
