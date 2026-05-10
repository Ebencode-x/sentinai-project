"""Tests for Milestone 3 (notifications) and Milestone 4 (observability metrics).

Coverage:
- MetricsCollector: record, snapshot, percentiles, fallback_rate, empty state
- notify routing: critical fires both channels, warning fires Slack only
- _build_slack_payload: Block Kit structure, confidence bar, flags
- _build_generic_payload: schema, flags, field mapping
- notifier silence: no env vars set -> no HTTP calls made
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.core.metrics import MetricsCollector
from src.integrations.notifier import (
    _build_generic_payload,
    _build_slack_payload,
    _send_generic_webhook,
    _send_slack,
    notify,
)
from src.models.events import LogIncident, RemediationSuggestion

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_incident(severity: str = "critical") -> LogIncident:
    return LogIncident(
        incident_id="test-fingerprint-01",
        detected_at_utc=datetime(2026, 5, 6, 12, 0, 0, tzinfo=UTC),
        severity=severity,
        trigger_line="ERROR unhandled exception in handler",
        stacktrace=(
            "ERROR unhandled exception\n"
            "Traceback (most recent call last):\n"
            "  File app.py line 42"
        ),
        context_before_error="INFO request received",
    )


def _make_suggestion(
    source: str = "provider",
    confidence: float = 0.85,
    provider_error: str | None = None,
) -> RemediationSuggestion:
    return RemediationSuggestion(
        summary="Unhandled exception in request handler.",
        proposed_code_fix="Wrap handler in try/except and return HTTP 500.",
        proposed_config_change="Set LOG_LEVEL=INFO in production.",
        confidence=confidence,
        risks="Ensure catch block does not swallow critical errors.",
        source=source,
        provider_error=provider_error,
        proposed_patch="try:\n    process()\nexcept Exception as e:\n    raise HTTPException(500)",
        test_guidance="1. Mock process() to raise. 2. Assert HTTP 500 returned.",
    )


# ---------------------------------------------------------------------------
# Milestone 4 -- MetricsCollector
# ---------------------------------------------------------------------------


def test_metrics_empty_snapshot_returns_none_latencies() -> None:
    m = MetricsCollector()
    snap = m.snapshot()
    assert snap["avg_latency_ms"] is None
    assert snap["p95_latency_ms"] is None
    assert snap["p99_latency_ms"] is None
    assert snap["fallback_rate"] == 0.0
    assert snap["total_suggestions"] == 0
    assert snap["latency_sample_count"] == 0


def test_metrics_records_provider_call() -> None:
    m = MetricsCollector()
    m.record(latency_ms=120.5, source="provider")
    assert m.total_suggestions == 1
    assert m.total_provider_calls == 1
    assert m.total_fallbacks == 0


def test_metrics_records_fallback_call() -> None:
    m = MetricsCollector()
    m.record(latency_ms=50.0, source="fallback")
    assert m.total_fallbacks == 1
    assert m.total_provider_calls == 1


def test_metrics_stub_does_not_increment_provider_calls() -> None:
    m = MetricsCollector()
    m.record(latency_ms=10.0, source="stub")
    assert m.total_provider_calls == 0
    assert m.total_suggestions == 1


def test_metrics_fallback_rate_calculated_correctly() -> None:
    m = MetricsCollector()
    m.record(latency_ms=100.0, source="provider")
    m.record(latency_ms=200.0, source="provider")
    m.record(latency_ms=50.0, source="fallback")
    snap = m.snapshot()
    assert abs(snap["fallback_rate"] - round(1 / 3, 4)) < 0.0001


def test_metrics_avg_latency_correct() -> None:
    m = MetricsCollector()
    m.record(latency_ms=100.0, source="provider")
    m.record(latency_ms=200.0, source="provider")
    m.record(latency_ms=300.0, source="provider")
    snap = m.snapshot()
    assert snap["avg_latency_ms"] == 200.0


def test_metrics_p95_with_enough_samples() -> None:
    m = MetricsCollector()
    for i in range(1, 21):
        m.record(latency_ms=float(i * 10), source="provider")
    snap = m.snapshot()
    assert snap["p95_latency_ms"] is not None
    assert snap["p95_latency_ms"] >= 150.0


def test_metrics_snapshot_sample_count_matches_records() -> None:
    m = MetricsCollector()
    for _ in range(5):
        m.record(latency_ms=75.0, source="stub")
    snap = m.snapshot()
    assert snap["latency_sample_count"] == 5


def test_metrics_thread_safe_no_exception_on_concurrent_writes() -> None:
    import threading

    m = MetricsCollector()
    errors: list[Exception] = []

    def worker() -> None:
        try:
            for _ in range(50):
                m.record(latency_ms=10.0, source="provider")
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert m.total_suggestions == 200


# ---------------------------------------------------------------------------
# Milestone 3 -- notify() routing
# ---------------------------------------------------------------------------


def test_notify_critical_calls_both_channels() -> None:
    incident = _make_incident(severity="critical")
    suggestion = _make_suggestion()
    with (
        patch("src.integrations.notifier._send_slack") as mock_slack,
        patch("src.integrations.notifier._send_generic_webhook") as mock_webhook,
    ):
        notify(incident, suggestion)
    mock_slack.assert_called_once_with(incident, suggestion)
    mock_webhook.assert_called_once_with(incident, suggestion)


def test_notify_warning_calls_slack_only() -> None:
    incident = _make_incident(severity="warning")
    suggestion = _make_suggestion()
    with (
        patch("src.integrations.notifier._send_slack") as mock_slack,
        patch("src.integrations.notifier._send_generic_webhook") as mock_webhook,
    ):
        notify(incident, suggestion)
    mock_slack.assert_called_once_with(incident, suggestion)
    mock_webhook.assert_not_called()


# ---------------------------------------------------------------------------
# Milestone 3 -- silence when env vars not set
# ---------------------------------------------------------------------------


def test_send_slack_does_nothing_when_url_not_set() -> None:
    with (
        patch("src.integrations.notifier.SLACK_WEBHOOK_URL", ""),
        patch("src.integrations.notifier.httpx") as mock_httpx,
    ):
        _send_slack(_make_incident(), _make_suggestion())
    mock_httpx.Client.assert_not_called()


def test_send_generic_webhook_does_nothing_when_url_not_set() -> None:
    with (
        patch("src.integrations.notifier.GENERIC_WEBHOOK_URL", ""),
        patch("src.integrations.notifier.httpx") as mock_httpx,
    ):
        _send_generic_webhook(_make_incident(), _make_suggestion())
    mock_httpx.Client.assert_not_called()


# ---------------------------------------------------------------------------
# Milestone 3 -- Slack Block Kit payload structure
# ---------------------------------------------------------------------------


def test_slack_payload_has_blocks_key() -> None:
    payload = _build_slack_payload(_make_incident(), _make_suggestion())
    assert "blocks" in payload
    assert isinstance(payload["blocks"], list)
    assert len(payload["blocks"]) >= 4


def test_slack_payload_header_contains_critical_label() -> None:
    payload = _build_slack_payload(_make_incident(severity="critical"), _make_suggestion())
    header = payload["blocks"][0]
    assert header["type"] == "header"
    assert "CRITICAL" in header["text"]["text"]


def test_slack_payload_header_contains_warning_label() -> None:
    payload = _build_slack_payload(_make_incident(severity="warning"), _make_suggestion())
    header = payload["blocks"][0]
    assert "WARNING" in header["text"]["text"]


def test_slack_payload_contains_incident_id() -> None:
    incident = _make_incident()
    payload = _build_slack_payload(incident, _make_suggestion())
    assert incident.incident_id in str(payload)


def test_slack_payload_low_confidence_adds_flag() -> None:
    payload = _build_slack_payload(_make_incident(), _make_suggestion(confidence=0.3))
    assert "Low confidence" in str(payload)


def test_slack_payload_normal_confidence_no_low_confidence_flag() -> None:
    payload = _build_slack_payload(_make_incident(), _make_suggestion(confidence=0.85))
    assert "Low confidence" not in str(payload)


def test_slack_payload_fallback_source_adds_degraded_flag() -> None:
    payload = _build_slack_payload(_make_incident(), _make_suggestion(source="fallback"))
    assert "Provider degraded" in str(payload)


def test_slack_payload_includes_patch_preview_when_present() -> None:
    payload = _build_slack_payload(_make_incident(), _make_suggestion())
    assert "Patch Preview" in str(payload)


def test_slack_payload_confidence_bar_length() -> None:
    for conf in (0.0, 0.5, 1.0):
        suggestion = _make_suggestion(confidence=conf)
        payload = _build_slack_payload(_make_incident(), suggestion)
        filled = round(conf * 10)
        bar = "\u2588" * filled + "\u2591" * (10 - filled)
        assert bar in str(payload)


# ---------------------------------------------------------------------------
# Milestone 3 -- generic webhook payload structure
# ---------------------------------------------------------------------------


def test_generic_payload_event_field() -> None:
    payload = _build_generic_payload(_make_incident(), _make_suggestion())
    assert payload["event"] == "sentinai.incident.detected"
    assert payload["schema_version"] == "1.0"


def test_generic_payload_incident_fields_present() -> None:
    incident = _make_incident()
    payload = _build_generic_payload(incident, _make_suggestion())
    inc = payload["incident"]
    assert inc["id"] == incident.incident_id
    assert inc["severity"] == "critical"
    assert inc["trigger_line"] == incident.trigger_line
    assert "detected_at_utc" in inc
    assert "stacktrace_preview" in inc


def test_generic_payload_suggestion_fields_present() -> None:
    suggestion = _make_suggestion()
    payload = _build_generic_payload(_make_incident(), suggestion)
    sug = payload["suggestion"]
    assert sug["source"] == "provider"
    assert sug["confidence"] == 0.85
    assert sug["proposed_patch"] is not None
    assert sug["test_guidance"] is not None


def test_generic_payload_low_confidence_flag() -> None:
    payload = _build_generic_payload(_make_incident(), _make_suggestion(confidence=0.4))
    assert "low_confidence" in payload["flags"]


def test_generic_payload_fallback_flag() -> None:
    payload = _build_generic_payload(_make_incident(), _make_suggestion(source="fallback"))
    assert "provider_degraded" in payload["flags"]


def test_generic_payload_no_flags_for_healthy_suggestion() -> None:
    payload = _build_generic_payload(
        _make_incident(), _make_suggestion(source="provider", confidence=0.85)
    )
    assert payload["flags"] == []


def test_generic_payload_stacktrace_preview_truncated() -> None:
    incident = _make_incident()
    incident = incident.model_copy(update={"stacktrace": "E " * 400})
    payload = _build_generic_payload(incident, _make_suggestion())
    assert len(payload["incident"]["stacktrace_preview"]) <= 500


# ---------------------------------------------------------------------------
# Milestone 3 -- HTTP call behaviour (mocked httpx)
# ---------------------------------------------------------------------------


def test_send_slack_posts_to_correct_url() -> None:
    mock_response = MagicMock()
    mock_response.is_success = True
    with (
        patch(
            "src.integrations.notifier.SLACK_WEBHOOK_URL",
            "https://hooks.slack.com/test",
        ),
        patch("src.integrations.notifier.httpx.Client") as mock_client_cls,
    ):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client
        _send_slack(_make_incident(), _make_suggestion())
    call_url = mock_client.post.call_args[0][0]
    assert call_url == "https://hooks.slack.com/test"


def test_send_slack_logs_warning_on_failure_status(
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock_response = MagicMock()
    mock_response.is_success = False
    mock_response.status_code = 400
    mock_response.text = "invalid_payload"
    with (
        patch(
            "src.integrations.notifier.SLACK_WEBHOOK_URL",
            "https://hooks.slack.com/test",
        ),
        patch("src.integrations.notifier.httpx.Client") as mock_client_cls,
    ):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client
        import logging

        with caplog.at_level(logging.WARNING, logger="src.integrations.notifier"):
            _send_slack(_make_incident(), _make_suggestion())
    assert any("Slack notification failed" in r.message for r in caplog.records)


def test_send_slack_does_not_raise_on_exception() -> None:
    with (
        patch(
            "src.integrations.notifier.SLACK_WEBHOOK_URL",
            "https://hooks.slack.com/test",
        ),
        patch(
            "src.integrations.notifier.httpx.Client",
            side_effect=Exception("network down"),
        ),
    ):
        _send_slack(_make_incident(), _make_suggestion())
