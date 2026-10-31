"""Settings and notification channels live in the database, channel URLs encrypted."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from src.core.crypto import KEY_ENV, SecretKeyError
from src.core.state import AppState
from src.db.models import NotificationChannel
from src.models.events import LogIncident, RemediationSuggestion

URL = "https://hooks.slack.com/services/T000/B000/SECRETVALUE1234"


def _channel(**extra) -> dict:
    return {"name": "Slack", "type": "slack", "url": URL, "severities": ["critical"], **extra}


def _broken_factory():
    raise RuntimeError("database down")


def _incident() -> LogIncident:
    return LogIncident(
        incident_id="fp-settings-1",
        detected_at_utc=datetime.now(UTC),
        trigger_line="KeyError: 'customer_id'",
        stacktrace="Traceback (most recent call last):",
    )


def _suggestion() -> RemediationSuggestion:
    return RemediationSuggestion(
        summary="Guard the lookup",
        proposed_code_fix="use dict.get",
        proposed_config_change="none",
        confidence=0.8,
        risks="low",
    )


def _legacy_file(tmp_path, state: AppState) -> object:
    state.watcher.config.log_file_path = str(tmp_path / "app.log")
    legacy = tmp_path / "settings.json"
    legacy.write_text(
        json.dumps(
            {
                "autonomy_mode": "auto_pr",
                "notification_channels": [
                    {
                        "id": "old",
                        "name": "Old",
                        "type": "webhook",
                        "url": "https://example.com/hook-abc",
                        "severities": ["warning"],
                        "enabled": True,
                    }
                ],
            }
        )
    )
    return legacy


def test_a_channel_is_stored_encrypted_and_returned_masked(app_db, secret_key):
    factory, _ = app_db
    state = AppState(session_factory=factory)
    channel = state.add_channel(_channel())
    assert "SECRETVALUE" not in channel["url"]
    assert channel["enabled"] is True
    with factory() as db:
        row = db.scalars(select(NotificationChannel)).one()
    assert "SECRETVALUE" not in row.url_encrypted
    assert row.url_encrypted != URL


def test_the_api_list_is_masked_but_delivery_gets_the_real_url(app_db, secret_key):
    factory, _ = app_db
    state = AppState(session_factory=factory)
    state.add_channel(_channel())
    assert "SECRETVALUE" not in state.channels()[0]["url"]
    assert state.delivery_channels()[0]["url"] == URL


def test_adding_a_channel_without_a_key_stores_nothing(app_db, monkeypatch):
    factory, _ = app_db
    monkeypatch.delenv(KEY_ENV, raising=False)
    state = AppState(session_factory=factory)
    with pytest.raises(SecretKeyError):
        state.add_channel(_channel())
    assert state.channels() == []


def test_update_keeps_the_url_unless_a_new_one_is_given(app_db, secret_key):
    factory, _ = app_db
    state = AppState(session_factory=factory)
    channel = state.add_channel(_channel())
    updated = state.update_channel(channel["id"], {"enabled": False, "name": "Renamed"})
    assert updated["enabled"] is False
    assert updated["name"] == "Renamed"
    assert state.delivery_channels()[0]["url"] == URL
    state.update_channel(channel["id"], {"url": "https://example.com/new-secret-9999"})
    assert state.delivery_channels()[0]["url"] == "https://example.com/new-secret-9999"


def test_sending_the_masked_url_back_does_not_overwrite_the_real_one(app_db, secret_key):
    factory, _ = app_db
    state = AppState(session_factory=factory)
    channel = state.add_channel(_channel())
    state.update_channel(channel["id"], {"url": channel["url"]})
    assert state.delivery_channels()[0]["url"] == URL


def test_unknown_channel_ids_are_reported(app_db, secret_key):
    factory, _ = app_db
    state = AppState(session_factory=factory)
    assert state.update_channel("nonexistent", {"enabled": False}) is None
    assert state.delete_channel("nonexistent") is False


def test_delete_removes_the_channel(app_db, secret_key):
    factory, _ = app_db
    state = AppState(session_factory=factory)
    channel = state.add_channel(_channel())
    assert state.delete_channel(channel["id"]) is True
    assert state.channels() == []


def test_a_channel_that_cannot_be_decrypted_is_skipped_not_fatal(app_db, secret_key, monkeypatch):
    factory, _ = app_db
    state = AppState(session_factory=factory)
    state.add_channel(_channel())
    monkeypatch.setenv(KEY_ENV, Fernet.generate_key().decode())
    assert state.delivery_channels() == []
    assert state.channels()[0]["url"] == "(encrypted)"


def test_delivery_channels_never_raise_when_the_database_is_down():
    assert AppState(session_factory=_broken_factory).delivery_channels() == []


def test_autonomy_mode_survives_a_restart(app_db):
    factory, _ = app_db
    state = AppState(session_factory=factory)
    state.set_autonomy_mode("auto_pr")
    assert AppState(session_factory=factory).current_autonomy_mode() == "auto_pr"
    state.set_autonomy_mode("propose_only")
    assert AppState(session_factory=factory).current_autonomy_mode() == "propose_only"


def test_an_invalid_autonomy_mode_is_rejected(app_db):
    factory, _ = app_db
    with pytest.raises(ValueError):
        AppState(session_factory=factory).set_autonomy_mode("yolo")


def test_autonomy_mode_falls_back_to_the_last_known_value_when_the_database_is_down():
    state = AppState(session_factory=_broken_factory)
    state.autonomy_mode = "auto_pr"
    assert state.current_autonomy_mode() == "auto_pr"


def test_a_scan_uses_the_stored_mode_and_the_real_channel_urls(app_db, secret_key):
    factory, _ = app_db
    state = AppState(session_factory=factory)
    state.set_autonomy_mode("auto_pr")
    state.add_channel(_channel())
    state.watcher.scan_once = lambda: [_incident()]
    state._record_audit = lambda incident, suggestion: None
    engine = MagicMock()
    engine.suggest_fix.return_value = _suggestion()
    state.remediation_engine = engine
    with patch("src.core.state.notify") as notify:
        state.scan_logs_once()
    assert engine.suggest_fix.call_args.kwargs["autonomy_mode"] == "auto_pr"
    assert notify.call_args.kwargs["channels"][0]["url"] == URL


def test_a_leftover_settings_file_is_imported_once_and_removed(app_db, secret_key, tmp_path):
    factory, _ = app_db
    state = AppState(session_factory=factory)
    legacy = _legacy_file(tmp_path, state)
    state.load_settings()
    assert not legacy.exists()
    assert state.current_autonomy_mode() == "auto_pr"
    assert [c["url"] for c in state.delivery_channels()] == ["https://example.com/hook-abc"]
    state.load_settings()
    assert len(state.channels()) == 1


def test_a_leftover_settings_file_stays_when_there_is_no_key(app_db, monkeypatch, tmp_path):
    factory, _ = app_db
    monkeypatch.delenv(KEY_ENV, raising=False)
    state = AppState(session_factory=factory)
    legacy = _legacy_file(tmp_path, state)
    state.load_settings()
    assert legacy.exists()
    assert state.channels() == []
