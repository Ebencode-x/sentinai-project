from src.api.audit_routes import build_feed


def _entry(**overrides):
    base = {
        "incident_id": "inc-1",
        "timestamp": "2026-10-27T10:00:00Z",
        "patch_hash": "h1",
        "failure_reason": None,
        "provider": "stub",
        "source": "stub",
        "model": "stub",
    }
    base.update(overrides)
    return base


def test_feed_exposes_model():
    feed = build_feed([_entry(model="claude-sonnet-4-20250514")], 5)
    assert feed[0]["model"] == "claude-sonnet-4-20250514"


def test_feed_model_none_for_legacy_entries():
    legacy = _entry()
    del legacy["model"]
    feed = build_feed([legacy], 5)
    assert feed[0]["model"] is None
