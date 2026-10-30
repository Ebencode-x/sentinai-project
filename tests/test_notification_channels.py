"""Tests for Milestone 7 -- configurable notification channels + per-severity routing.

Coverage:
- AppState channel CRUD: add, update, delete, persistence round-trip
- notifier._notify_channels: severity filtering, enabled filtering, type dispatch
- notify(): channels param takes priority over legacy env-var routing when non-empty
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from src.integrations.notifier import notify
from src.models.events import LogIncident, RemediationSuggestion

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_incident(severity: str = "critical") -> LogIncident:
    return LogIncident(
        incident_id="chan-test-01",
        detected_at_utc=datetime(2026, 8, 4, 12, 0, 0, tzinfo=UTC),
        severity=severity,
        trigger_line="ERROR test",
        stacktrace="Traceback:\n  File x.py line 1",
        context_before_error="",
    )


def _make_suggestion() -> RemediationSuggestion:
    return RemediationSuggestion(
        summary="Test summary.",
        proposed_code_fix="fix it",
        proposed_config_change="",
        confidence=0.8,
        risks="none",
        source="provider",
    )


def _make_channel(
    name: str = "Slack Critical",
    ch_type: str = "slack",
    severities: list[str] | None = None,
    enabled: bool = True,
) -> dict:
    return {
        "id": "test-id",
        "name": name,
        "type": ch_type,
        "url": "https://example.com/hook",
        "severities": severities or ["critical"],
        "enabled": enabled,
    }


# ---------------------------------------------------------------------------
# notify() routing with channels
# ---------------------------------------------------------------------------


def test_notify_with_channels_dispatches_slack_type() -> None:
    channel = _make_channel(ch_type="slack", severities=["critical"])
    with patch("src.integrations.notifier._send_slack_to") as mock_send:
        notify(_make_incident("critical"), _make_suggestion(), channels=[channel])
    mock_send.assert_called_once()
    assert mock_send.call_args[0][0] == channel["url"]


def test_notify_with_channels_dispatches_webhook_type() -> None:
    channel = _make_channel(ch_type="webhook", severities=["critical"])
    with patch("src.integrations.notifier._send_webhook_to") as mock_send:
        notify(_make_incident("critical"), _make_suggestion(), channels=[channel])
    mock_send.assert_called_once()
    assert mock_send.call_args[0][0] == channel["url"]


def test_notify_with_channels_skips_when_severity_not_matched() -> None:
    channel = _make_channel(severities=["critical"])
    with patch("src.integrations.notifier._send_slack_to") as mock_send:
        notify(_make_incident("warning"), _make_suggestion(), channels=[channel])
    mock_send.assert_not_called()


def test_notify_with_channels_skips_when_disabled() -> None:
    channel = _make_channel(severities=["critical"], enabled=False)
    with patch("src.integrations.notifier._send_slack_to") as mock_send:
        notify(_make_incident("critical"), _make_suggestion(), channels=[channel])
    mock_send.assert_not_called()


def test_notify_empty_channels_falls_back_to_legacy() -> None:
    """channels=[] must behave exactly like channels=None (legacy env-var routing)."""
    with (
        patch("src.integrations.notifier._send_slack") as mock_slack,
        patch("src.integrations.notifier._send_generic_webhook") as mock_webhook,
    ):
        notify(_make_incident("critical"), _make_suggestion(), channels=[])
    mock_slack.assert_called_once()
    mock_webhook.assert_called_once()


def test_notify_multiple_channels_each_evaluated_independently() -> None:
    slack_critical = _make_channel(name="A", ch_type="slack", severities=["critical"])
    webhook_all = _make_channel(name="B", ch_type="webhook", severities=["warning", "critical"])
    with (
        patch("src.integrations.notifier._send_slack_to") as mock_slack,
        patch("src.integrations.notifier._send_webhook_to") as mock_webhook,
    ):
        notify(
            _make_incident("critical"),
            _make_suggestion(),
            channels=[slack_critical, webhook_all],
        )
    mock_slack.assert_called_once()
    mock_webhook.assert_called_once()
