"""Tests for the webhook dispatcher (WebhookDispatcher, WebhookEvent)."""

from __future__ import annotations

import json
from unittest.mock import patch

from src.api.webhooks import WebhookDispatcher, WebhookEvent, dispatch_webhook

# ===========================================================================
# WEBHOOKS
# ===========================================================================


class TestWebhookDispatcher:
    def test_no_urls_returns_empty_list(self, monkeypatch):
        monkeypatch.delenv("SENTINAI_WEBHOOK_URLS", raising=False)
        d = WebhookDispatcher()
        result = d.dispatch(WebhookEvent.INCIDENT_DETECTED, {"id": "abc"})
        assert result == []

    def test_dispatch_posts_correct_shape(self, monkeypatch):
        monkeypatch.setenv("SENTINAI_WEBHOOK_URLS", "https://hooks.example.com/test")
        captured: list[dict] = []

        def fake_post(url: str, body_bytes: bytes) -> bool:
            captured.append(json.loads(body_bytes))
            return True

        d = WebhookDispatcher()
        with patch.object(d, "_post", side_effect=fake_post):
            d.dispatch(WebhookEvent.INCIDENT_DETECTED, {"incident_id": "xyz"})

        assert len(captured) == 1
        body = captured[0]
        assert body["event"] == "incident.detected"
        assert "timestamp" in body
        assert body["payload"]["incident_id"] == "xyz"

    def test_dispatch_returns_succeeded_urls(self, monkeypatch):
        monkeypatch.setenv(
            "SENTINAI_WEBHOOK_URLS",
            "https://hooks.a.com,https://hooks.b.com",
        )
        d = WebhookDispatcher()
        with patch.object(d, "_post", return_value=True):
            result = d.dispatch(WebhookEvent.PATCH_APPLIED, {})
        assert len(result) == 2

    def test_failed_url_not_in_succeeded(self, monkeypatch):
        monkeypatch.setenv("SENTINAI_WEBHOOK_URLS", "https://hooks.fail.com")
        d = WebhookDispatcher()
        with patch.object(d, "_post", return_value=False):
            result = d.dispatch(WebhookEvent.PATCH_APPLIED, {})
        assert result == []

    def test_http_error_does_not_raise(self, monkeypatch):
        monkeypatch.setenv("SENTINAI_WEBHOOK_URLS", "https://hooks.example.com")
        import urllib.error
        import urllib.request

        d = WebhookDispatcher()
        with patch(
            "urllib.request.urlopen", side_effect=urllib.error.HTTPError(None, 500, "err", {}, None)
        ):
            # Must not raise — errors are caught inside _post
            d.dispatch(WebhookEvent.INCIDENT_DETECTED, {})

    def test_timeout_does_not_raise(self, monkeypatch):
        monkeypatch.setenv("SENTINAI_WEBHOOK_URLS", "https://hooks.example.com")
        d = WebhookDispatcher()
        with patch("urllib.request.urlopen", side_effect=TimeoutError):
            d.dispatch(WebhookEvent.INCIDENT_DETECTED, {})

    def test_invalid_url_ignored(self, monkeypatch):
        monkeypatch.setenv("SENTINAI_WEBHOOK_URLS", "not-a-url,ftp://bad")
        d = WebhookDispatcher()
        with patch.object(d, "_post", return_value=True) as mock_post:
            d.dispatch(WebhookEvent.INCIDENT_DETECTED, {})
        mock_post.assert_not_called()

    def test_mixed_valid_invalid_urls(self, monkeypatch):
        monkeypatch.setenv(
            "SENTINAI_WEBHOOK_URLS",
            "not-valid,https://good.example.com",
        )
        d = WebhookDispatcher()
        with patch.object(d, "_post", return_value=True) as mock_post:
            d.dispatch(WebhookEvent.PATCH_APPLIED, {})
        mock_post.assert_called_once()

    def test_all_event_types_dispatch(self, monkeypatch):
        monkeypatch.setenv("SENTINAI_WEBHOOK_URLS", "https://hooks.example.com")
        d = WebhookDispatcher()
        with patch.object(d, "_post", return_value=True):
            for event in WebhookEvent:
                result = d.dispatch(event, {"test": True})
                assert isinstance(result, list)

    def test_module_level_dispatch_webhook(self, monkeypatch):
        monkeypatch.delenv("SENTINAI_WEBHOOK_URLS", raising=False)
        result = dispatch_webhook(WebhookEvent.INJECTION_BLOCKED, {"field": "trigger_line"})
        assert result == []


class TestWebhookEvent:
    def test_event_values(self):
        assert WebhookEvent.INCIDENT_DETECTED == "incident.detected"
        assert WebhookEvent.SUGGESTION_GENERATED == "suggestion.generated"
        assert WebhookEvent.PATCH_APPLIED == "patch.applied"
        assert WebhookEvent.INJECTION_BLOCKED == "injection.blocked"
        assert WebhookEvent.POLICY_BLOCKED == "policy.blocked"

    def test_all_events_are_strings(self):
        for event in WebhookEvent:
            assert isinstance(event, str)
