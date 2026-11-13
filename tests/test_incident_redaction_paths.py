"""Secrets are masked on the watcher and notifier paths."""

import inspect
from collections import deque
from datetime import UTC, datetime
from unittest.mock import MagicMock

from src.integrations import notifier
from src.models.events import LogIncident
from src.services import watcher as watcher_mod
from src.services.incident_redaction import redact_text

SNL = "snl_" + "a1B2c3D4" * 5
BEARER = "Bearer abcDEF123456abcDEF123456abcDEF"
RAW = (SNL, "abcDEF123456abcDEF123456abcDEF")


def test_patterns_catch_the_test_secrets():
    assert redact_text(f"key {SNL}")[1] >= 1
    assert redact_text(f"Authorization: {BEARER}")[1] >= 1


def _watcher():
    cls = next(
        obj
        for _, obj in inspect.getmembers(watcher_mod, inspect.isclass)
        if "_build_incident" in vars(obj)
    )
    instance = object.__new__(cls)
    instance._context_buffer = deque([f"context key {SNL}"])
    return instance


def test_watcher_incident_has_no_secrets_and_keeps_id():
    w = _watcher()
    block = [f"ERROR boot failed key={SNL}", f"  header Authorization: {BEARER}"]
    incident = w._build_incident(block)
    for field in (incident.trigger_line, incident.stacktrace, incident.context_before_error):
        for raw in RAW:
            assert raw not in field
    assert incident.incident_id == w._fingerprint("\n".join(block))


def _incident():
    return LogIncident(
        incident_id="abc123",
        detected_at_utc=datetime.now(UTC),
        severity="critical",
        trigger_line=f"ERROR key={SNL}",
        stacktrace=f"Traceback\n  Authorization: {BEARER}",
        context_before_error="",
    )


def test_notify_legacy_path_sends_clean_incident(monkeypatch):
    seen = []
    monkeypatch.setattr(notifier, "_send_slack", lambda i, s: seen.append(i))
    monkeypatch.setattr(notifier, "_send_generic_webhook", lambda i, s: seen.append(i))
    notifier.notify(_incident(), MagicMock())
    assert len(seen) == 2
    for incident in seen:
        for raw in RAW:
            assert raw not in incident.trigger_line
            assert raw not in incident.stacktrace
        assert incident.incident_id == "abc123"


def test_notify_channel_path_sends_clean_incident(monkeypatch):
    seen = []
    monkeypatch.setattr(notifier, "_send_slack_to", lambda url, i, s: seen.append(i))
    channels = [
        {
            "type": "slack",
            "url": "https://hooks.example/x",
            "enabled": True,
            "severities": ["critical"],
        }
    ]
    notifier.notify(_incident(), MagicMock(), channels)
    assert len(seen) == 1
    for raw in RAW:
        assert raw not in seen[0].trigger_line
        assert raw not in seen[0].stacktrace
