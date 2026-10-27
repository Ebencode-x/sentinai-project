import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.api.audit_routes as audit_routes
from src.api.audit_routes import build_feed, router
from src.api.deps import require_user
from src.core.audit import AuditLogger


def _entry(**kw):
    base = {
        "timestamp": "2026-10-23T10:00:00.000+00:00",
        "incident_id": "inc-1",
        "provider": "stub",
        "patch_file": "src/app.py",
        "patch_hash": "sha256:aaa",
        "policy_decision": "allow",
        "risk_tier": "low",
        "review_required": False,
        "patch_applied": False,
        "pr_url": None,
        "failure_reason": None,
        "confidence": 0.8,
        "source": "stub",
    }
    base.update(kw)
    return base


def test_duplicates_are_collapsed_with_count():
    reason = "[D2] Sandbox unavailable"
    entries = [_entry(failure_reason=reason)] * 3 + [_entry(incident_id="inc-2")]
    feed = build_feed(entries, limit=10)
    assert len(feed) == 2
    blocked = [e for e in feed if e["incident_id"] == "inc-1"][0]
    assert blocked["count"] == 3
    assert blocked["title"] == "Patch not applied"
    assert blocked["level"] == "warning"


def test_newest_first_and_limit():
    entries = [
        _entry(incident_id=f"inc-{i}", timestamp=f"2026-10-23T10:0{i}:00+00:00") for i in range(5)
    ]
    feed = build_feed(entries, limit=2)
    assert [e["incident_id"] for e in feed] == ["inc-4", "inc-3"]


def test_classification():
    applied = build_feed([_entry(patch_applied=True, pr_url="https://x/pr/1")], 5)
    assert applied[0]["level"] == "success"
    assert "pull request" in applied[0]["title"]
    denied = build_feed([_entry(policy_decision="deny")], 5)
    assert denied[0]["level"] == "danger"
    review = build_feed([_entry(review_required=True)], 5)
    assert review[0]["title"] == "Waiting for review"


def test_route_returns_feed(monkeypatch):
    entries = [_entry(), _entry(incident_id="inc-2")]
    monkeypatch.setattr(
        audit_routes.audit_logger, "tail_rows", lambda n=50, archived=False: entries
    )
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[require_user] = lambda: None
    client = TestClient(app)
    res = client.get("/api/audit?limit=1")
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert client.get("/api/audit?limit=0").status_code == 422


def test_tail_skips_bad_lines_and_respects_n(tmp_path):
    path = tmp_path / "audit.jsonl"
    rows = [json.dumps({"incident_id": f"i{i}"}) for i in range(6)]
    rows.insert(3, "{not json")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    log = AuditLogger(log_path=path)
    tail = log.tail(n=3)
    assert [e["incident_id"] for e in tail] == ["i3", "i4", "i5"]
    assert log.tail(n=100)[0]["incident_id"] == "i0"
