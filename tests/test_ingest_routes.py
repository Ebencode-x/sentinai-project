"""Tests for POST /api/ingest."""

import threading
import traceback
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.api.ingest_routes as ingest
from src.core.rate_limiter import TokenBucket
from src.core.state import app_state
from src.services.watcher import LogWatcher, WatcherConfig

KEY = "k" * 32


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    log = tmp_path / "app.log"
    watcher = LogWatcher(WatcherConfig(log_file_path=str(log)))
    watcher.initialize_position(start_from_end=True)
    scans: list[int] = []
    monkeypatch.setattr(app_state, "watcher", watcher)
    monkeypatch.setattr(app_state, "scan_logs_once", lambda: scans.append(1) or 0)
    monkeypatch.setenv("SENTINAI_INGEST_KEY", KEY)
    monkeypatch.setattr(ingest, "_ingest_limiter", TokenBucket(100, 100))
    monkeypatch.setattr(ingest, "_scan_flag", threading.Lock())
    app = FastAPI()
    app.include_router(ingest.router, prefix="/api")
    return TestClient(app), log, scans


def _post(client, events, *, source="agrolink", key=KEY):
    headers = {} if key is None else {"X-Ingest-Key": key}
    return client.post("/api/ingest", json={"source": source, "events": events}, headers=headers)


def _boom() -> None:
    raise KeyError("missing")


def _real_traceback() -> str:
    try:
        _boom()
    except KeyError:
        return traceback.format_exc()
    raise AssertionError("unreachable")


def _incidents(log: Path):
    fresh = LogWatcher(WatcherConfig(log_file_path=str(log)))
    fresh.initialize_position(start_from_end=False)
    return fresh.scan_once()


def test_not_configured_returns_503(env, monkeypatch):
    client, log, scans = env
    monkeypatch.delenv("SENTINAI_INGEST_KEY")
    assert _post(client, [{"message": "boom"}]).status_code == 503
    assert log.read_text() == ""
    assert scans == []


def test_short_key_counts_as_not_configured(env, monkeypatch):
    client, log, _ = env
    monkeypatch.setenv("SENTINAI_INGEST_KEY", "short")
    assert _post(client, [{"message": "boom"}], key="short").status_code == 503
    assert log.read_text() == ""


@pytest.mark.parametrize("key", [None, "wrong-key", "k" * 31])
def test_bad_key_is_rejected(env, key):
    client, log, scans = env
    assert _post(client, [{"message": "boom"}], key=key).status_code == 401
    assert log.read_text() == ""
    assert scans == []


def test_valid_event_is_written_and_scan_scheduled(env):
    client, log, scans = env
    resp = _post(client, [{"message": "boom"}])
    assert resp.status_code == 202
    assert resp.json() == {"accepted": 1, "source": "agrolink"}
    assert log.read_text() == "ERROR [agrolink] boom\n"
    assert scans == [1]


def test_ingested_traceback_becomes_a_single_incident(env):
    client, log, _ = env
    event = {"message": "boom", "traceback": _real_traceback()}
    assert _post(client, [event]).status_code == 202
    incidents = _incidents(log)
    assert len(incidents) == 1
    assert "[agrolink]" in incidents[0].trigger_line
    assert "KeyError: 'missing'" in incidents[0].stacktrace


def test_client_cannot_forge_log_lines(env):
    client, log, _ = env
    evil_trace = (
        "Traceback (most recent call last):\n"
        '  File "x.py", line 1, in f\n'
        "ERROR [other] forged\n"
        "KeyError: 'x'"
    )
    event = {"message": "first\nERROR [evil] injected", "traceback": evil_trace}
    assert _post(client, [event]).status_code == 202
    lines = log.read_text().splitlines()
    assert sum(line.startswith("ERROR [") for line in lines) == 1
    assert len(_incidents(log)) == 1


def test_personal_data_is_masked(env):
    client, log, _ = env
    message = (
        "Payment failed for a@b.com phone 0712345678 and +255712345678 from 10.0.0.5 OTP=123456"
    )
    trace = (
        "sqlalchemy.exc.IntegrityError: duplicate\n"
        "DETAIL:  Key (email)=(a@b.com) already exists.\n"
        "[SQL: INSERT INTO users (email) VALUES (%(email)s)]\n"
        "[parameters: {'email': 'a@b.com', 'name': 'Juma'}]"
    )
    assert _post(client, [{"message": message, "traceback": trace}]).status_code == 202
    text = log.read_text()
    for secret in ("a@b.com", "0712345678", "712345678", "10.0.0.5", "123456", "Juma"):
        assert secret not in text
    assert "ERROR [agrolink] Payment failed" in text


def test_secrets_are_masked(env):
    client, log, _ = env
    message = "call failed Authorization: Bearer abc.def.ghi password=hunter2"
    assert _post(client, [{"message": message}]).status_code == 202
    text = log.read_text()
    assert "abc.def.ghi" not in text
    assert "hunter2" not in text


@pytest.mark.parametrize(
    "payload",
    [
        {"source": "Bad Source", "events": [{"message": "x"}]},
        {"source": "agrolink", "events": []},
        {"source": "agrolink", "events": [{"message": "x"}] * 21},
        {"source": "agrolink", "events": [{"message": "x" * 1001}]},
        {"source": "agrolink", "events": [{"message": "x", "traceback": "t" * 6001}]},
        {"source": "agrolink"},
    ],
)
def test_invalid_payload_is_rejected(env, payload):
    client, log, _ = env
    resp = client.post("/api/ingest", json=payload, headers={"X-Ingest-Key": KEY})
    assert resp.status_code == 422
    assert log.read_text() == ""


def test_oversized_body_is_rejected(env):
    client, log, _ = env
    body = (
        b'{"source": "agrolink", "events": [{"message": "'
        + b"x" * (ingest._MAX_BODY_BYTES + 10)
        + b'"}]}'
    )
    resp = client.post(
        "/api/ingest",
        content=body,
        headers={"X-Ingest-Key": KEY, "Content-Type": "application/json"},
    )
    assert resp.status_code == 413
    assert log.read_text() == ""


def test_rate_limit_returns_429(env, monkeypatch):
    client, _, _ = env
    monkeypatch.setattr(ingest, "_ingest_limiter", TokenBucket(1, 1))
    assert _post(client, [{"message": "one"}]).status_code == 202
    second = _post(client, [{"message": "two"}])
    assert second.status_code == 429
    assert second.headers["Retry-After"] == "60"


def test_long_traceback_is_trimmed_to_one_block(env):
    client, log, _ = env
    frames = "".join(f'  File "a.py", line {i}, in f{i}\n    call()\n' for i in range(100))
    trace = "Traceback (most recent call last):\n" + frames + "KeyError: 'x'"
    assert _post(client, [{"message": "deep", "traceback": trace}]).status_code == 202
    lines = log.read_text().splitlines()
    assert len(lines) == 31
    assert any("lines omitted" in line for line in lines)
    assert lines[-1] == "KeyError: 'x'"
    assert len(_incidents(log)) == 1


def test_log_is_truncated_at_the_size_cap(env, monkeypatch):
    client, log, _ = env
    monkeypatch.setattr(ingest, "_MAX_LOG_BYTES", 300)
    _post(client, [{"message": "A" * 200}])
    _post(client, [{"message": "B" * 200}])
    text = log.read_text()
    assert "B" * 200 in text
    assert "A" * 200 not in text
    assert len(app_state.watcher.scan_once()) == 1


def test_scan_is_not_queued_twice_while_one_is_pending(env):
    client, _, scans = env
    assert ingest._scan_flag.acquire(blocking=False)
    assert _post(client, [{"message": "one"}]).status_code == 202
    assert scans == []
    ingest._scan_flag.release()
    assert _post(client, [{"message": "two"}]).status_code == 202
    assert scans == [1]
