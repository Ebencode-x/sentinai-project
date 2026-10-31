"""POST /api/v1/events: per-source keys, storage before the reply, no double counting."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from src.api import event_routes as events
from src.db import sources
from src.db.models import IngestedEvent, Source
from src.db.session import get_db

URL = "/api/v1/events"


@pytest.fixture
def env(app_db, monkeypatch):
    factory, account_id = app_db

    def session():
        with factory() as db:
            yield db

    app = FastAPI()
    app.include_router(events.router, prefix="/api")
    app.dependency_overrides[get_db] = session
    monkeypatch.setattr(events, "_limiters", {})
    with factory() as db:
        source, key = sources.create_source(db, account_id, "agrolink")
        source_id = source.id
    return SimpleNamespace(
        client=TestClient(app),
        factory=factory,
        key=key,
        source_id=source_id,
        account_id=account_id,
    )


def _auth(key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}


def _post(client, key, batch, **extra):
    return client.post(URL, json={"events": batch, **extra}, headers=_auth(key))


def _stored(factory):
    with factory() as db:
        return list(db.scalars(select(IngestedEvent).order_by(IngestedEvent.received_at)).all())


def test_a_valid_batch_is_stored_and_attributed_to_the_key_owner(env):
    batch = [
        {
            "message": "KeyError: 'customer_id'",
            "environment": "production",
            "release": "abc123",
            "request_id": "r-1",
        },
        {"message": "second", "level": "warning"},
    ]
    response = _post(env.client, env.key, batch, source="someone-else")
    assert response.status_code == 202
    assert response.json() == {"accepted": 2, "duplicates": 0}
    rows = _stored(env.factory)
    assert {row.source_id for row in rows} == {env.source_id}
    first = next(row for row in rows if row.message.startswith("KeyError"))
    assert (first.level, first.environment, first.release, first.request_id) == (
        "error",
        "production",
        "abc123",
        "r-1",
    )
    assert first.processed_at is None
    assert first.fingerprint


@pytest.mark.parametrize(
    "header",
    [None, "", "Bearer", "Bearer snl_00000000_" + "A" * 43, "Basic abc", "snl_x"],
)
def test_missing_or_wrong_credentials_are_refused_and_nothing_is_stored(env, header):
    headers = {} if header is None else {"Authorization": header}
    response = env.client.post(URL, json={"events": [{"message": "x"}]}, headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert _stored(env.factory) == []


def test_a_revoked_key_is_refused(env):
    with env.factory() as db:
        sources.revoke_source(db, env.account_id, env.source_id)
    assert _post(env.client, env.key, [{"message": "x"}]).status_code == 401
    assert _stored(env.factory) == []


def test_the_bearer_scheme_is_case_insensitive(env):
    headers = {"Authorization": f"bearer {env.key}"}
    response = env.client.post(URL, json={"events": [{"message": "x"}]}, headers=headers)
    assert response.status_code == 202


@pytest.mark.parametrize(
    "body",
    [
        {"events": []},
        {"events": [{"message": ""}]},
        {"events": [{"message": "x", "level": "info"}]},
        {"events": [{"message": "x", "event_id": "has space"}]},
        {"events": [{"message": "x", "environment": "Prod uction"}]},
        {"events": [{"message": "x"}] * 101},
        {"events": [{"message": "x" * 2001}]},
        {"nothing": True},
    ],
)
def test_invalid_events_are_rejected_with_422(env, body):
    response = env.client.post(URL, json=body, headers=_auth(env.key))
    assert response.status_code == 422
    assert _stored(env.factory) == []


def test_a_body_that_is_not_json_is_rejected(env):
    headers = {**_auth(env.key), "Content-Type": "application/json"}
    assert env.client.post(URL, content=b"not json", headers=headers).status_code == 422


def test_an_oversized_body_is_rejected(env):
    response = _post(env.client, env.key, [{"message": "x"}], pad="x" * 300_000)
    assert response.status_code == 413
    assert _stored(env.factory) == []


def test_a_retry_with_the_same_event_id_is_not_stored_twice(env):
    event = {"message": "boom", "event_id": "evt-1"}
    first = _post(env.client, env.key, [event])
    second = _post(env.client, env.key, [event])
    assert first.json() == {"accepted": 1, "duplicates": 0}
    assert second.json() == {"accepted": 0, "duplicates": 1}
    assert len(_stored(env.factory)) == 1


def test_a_repeated_id_inside_one_batch_is_counted_once(env):
    batch = [{"message": "a", "event_id": "e"}, {"message": "b", "event_id": "e"}]
    assert _post(env.client, env.key, batch).json() == {"accepted": 1, "duplicates": 1}


def test_events_without_an_id_are_always_stored(env):
    _post(env.client, env.key, [{"message": "boom"}])
    _post(env.client, env.key, [{"message": "boom"}])
    assert len(_stored(env.factory)) == 2


def test_personal_data_is_masked_before_storage(env):
    trace = "\n".join(
        [
            "Traceback (most recent call last):",
            '  File "a.py", line 1, in f',
            "ValueError: password=hunter2",
        ]
    )
    batch = [
        {
            "message": "login failed for farmer@example.com phone 0712345678 from 10.1.2.3",
            "stacktrace": trace,
        }
    ]
    _post(env.client, env.key, batch)
    row = _stored(env.factory)[0]
    for secret in ("farmer@example.com", "0712345678", "10.1.2.3", "hunter2"):
        assert secret not in row.message
        assert secret not in (row.stacktrace or "")
    assert "<email>" in row.message


def test_the_same_crash_with_different_numbers_shares_a_fingerprint(env):
    batch = [
        {"message": "Order 123 not found"},
        {"message": "Order 456 not found"},
        {"message": "Customer missing"},
    ]
    _post(env.client, env.key, batch)
    prints = {row.message: row.fingerprint for row in _stored(env.factory)}
    assert prints["Order 123 not found"] == prints["Order 456 not found"]
    assert prints["Order 123 not found"] != prints["Customer missing"]


def test_timestamps_are_clamped_and_made_timezone_aware(env):
    batch = [
        {"message": "future", "timestamp": "2099-01-01T00:00:00Z"},
        {"message": "naive", "timestamp": "2020-05-06T07:08:09"},
    ]
    _post(env.client, env.key, batch)
    rows = {row.message: row for row in _stored(env.factory)}
    assert abs(datetime.now(UTC) - rows["future"].occurred_at) < timedelta(minutes=1)
    assert rows["naive"].occurred_at == datetime(2020, 5, 6, 7, 8, 9, tzinfo=UTC)


def test_the_sources_last_event_time_is_recorded(env):
    with env.factory() as db:
        assert db.get(Source, env.source_id).last_event_at is None
    _post(env.client, env.key, [{"message": "boom"}])
    with env.factory() as db:
        assert db.get(Source, env.source_id).last_event_at is not None


def test_a_source_is_throttled_on_its_own(env, monkeypatch):
    monkeypatch.setattr(events, "_RATE_PER_MINUTE", 2)
    responses = [_post(env.client, env.key, [{"message": "x"}]) for _ in range(3)]
    assert [r.status_code for r in responses] == [202, 202, 429]
    assert responses[-1].headers["retry-after"] == "60"
    with env.factory() as db:
        _other, other_key = sources.create_source(db, env.account_id, "orders-api")
    assert _post(env.client, other_key, [{"message": "x"}]).status_code == 202


def test_a_storage_failure_is_a_503_so_the_sender_retries(env, monkeypatch):
    def boom(*_args, **_kwargs):
        raise OperationalError("insert", {}, Exception("database down"))

    monkeypatch.setattr(events.event_store, "store_events", boom)
    response = _post(env.client, env.key, [{"message": "x"}])
    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"


def test_the_route_is_mounted_in_the_app_and_needs_a_key():
    from src.main import app

    response = TestClient(app).post(URL, json={"events": [{"message": "x"}]})
    assert response.status_code == 401
