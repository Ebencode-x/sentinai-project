"""Archive, restore and permanent delete of audit events."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from src.api import audit_routes
from src.api.deps import require_user
from src.core.audit import AuditLogger
from src.db.models import Base, Role


def _record(log: AuditLogger, incident_id: str) -> None:
    log.record(
        incident_id=incident_id,
        model="stub",
        provider="stub",
        patch_file=None,
        patch=None,
        policy_decision=None,
        risk_tier=None,
        review_required=True,
        patch_applied=False,
        tests_passed=None,
        pr_url=None,
        failure_reason=None,
        confidence=0.6,
        source="stub",
    )


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pg_engine):
    Base.metadata.create_all(pg_engine)
    log = AuditLogger(
        tmp_path / "audit.jsonl",
        session_factory=sessionmaker(pg_engine, expire_on_commit=False),
    )
    monkeypatch.setattr(audit_routes, "audit_logger", log)
    current = {"role": Role.ADMIN}
    app = FastAPI()
    app.include_router(audit_routes.router, prefix="/api")
    app.dependency_overrides[require_user] = lambda: SimpleNamespace(
        email="admin@test", role=current["role"]
    )
    return log, TestClient(app), current


def _incidents(client: TestClient, **params: str) -> list[str]:
    feed = client.get("/api/audit", params=params).json()
    return [e["incident_id"] for e in feed]


def test_feed_carries_row_ids(env) -> None:
    log, client, _ = env
    _record(log, "inc-a")
    feed = client.get("/api/audit").json()
    assert len(feed) == 1
    assert len(feed[0]["row_ids"]) == 1


def test_archive_hides_event_and_restore_brings_it_back(env) -> None:
    log, client, _ = env
    _record(log, "inc-a")
    _record(log, "inc-b")
    feed = client.get("/api/audit").json()
    target = next(e for e in feed if e["incident_id"] == "inc-a")

    resp = client.post("/api/audit/archive", json={"ids": target["row_ids"]})
    assert resp.status_code == 200
    assert resp.json() == {"changed": 1}
    assert _incidents(client) == ["inc-b"]

    archived = client.get("/api/audit", params={"archived": "true"}).json()
    assert [e["incident_id"] for e in archived] == ["inc-a"]
    assert archived[0]["archived_by"] == "admin@test"

    client.post("/api/audit/restore", json={"ids": target["row_ids"]})
    assert sorted(_incidents(client)) == ["inc-a", "inc-b"]
    assert _incidents(client, archived="true") == []


def test_archiving_a_collapsed_event_hides_every_row(env) -> None:
    log, client, _ = env
    _record(log, "inc-a")
    _record(log, "inc-a")
    feed = client.get("/api/audit").json()
    assert feed[0]["count"] == 2
    assert len(feed[0]["row_ids"]) == 2

    client.post("/api/audit/archive", json={"ids": feed[0]["row_ids"]})
    # Nothing left in the feed, and the log file must not bring it back.
    assert client.get("/api/audit").json() == []


def test_delete_only_removes_archived_events(env) -> None:
    log, client, _ = env
    _record(log, "inc-a")
    ids = client.get("/api/audit").json()[0]["row_ids"]

    assert client.post("/api/audit/delete", json={"ids": ids}).json() == {"changed": 0}
    assert _incidents(client) == ["inc-a"]

    client.post("/api/audit/archive", json={"ids": ids})
    assert client.post("/api/audit/delete", json={"ids": ids}).json() == {"changed": 1}
    assert _incidents(client, archived="true") == []
    assert _incidents(client) == []


def test_viewer_cannot_archive_restore_or_delete(env) -> None:
    log, client, current = env
    _record(log, "inc-a")
    current["role"] = Role.VIEWER
    for action in ("archive", "restore", "delete"):
        resp = client.post(f"/api/audit/{action}", json={"ids": [1]})
        assert resp.status_code == 403
    assert client.get("/api/audit").status_code == 200


def test_ids_are_required(env) -> None:
    _, client, _ = env
    assert client.post("/api/audit/archive", json={"ids": []}).status_code == 422
