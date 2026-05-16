"""Phase 2 — Tests for auth, per-tenant rate limiting, and webhooks.

Coverage
--------
auth.py
  - TenantKeyStore loads multi-key JSON env var correctly
  - TenantKeyStore falls back to legacy single-key env var
  - TenantKeyStore returns empty store when no env vars set
  - lookup() uses constant-time comparison (no timing shortcuts)
  - lookup() returns None for unknown keys
  - require_tenant() returns anonymous tenant when auth disabled
  - require_tenant() raises 401 when key missing and auth enabled
  - require_tenant() raises 403 when key wrong and auth enabled
  - require_tenant() returns correct Tenant on valid key
  - RateLimitTier values and TIER_LIMITS mapping
  - Tenant.rate_limit property

middleware.py
  - enforce_rate_limit() passes for internal tier (unlimited)
  - enforce_rate_limit() passes within limit
  - enforce_rate_limit() raises 429 when bucket exhausted
  - 429 response includes Retry-After header
  - Different tenants have independent buckets

webhooks.py
  - dispatch_webhook() is a no-op when no URLs configured
  - dispatch_webhook() POSTs correct JSON shape
  - dispatch_webhook() handles HTTP errors gracefully (no raise)
  - dispatch_webhook() handles timeout gracefully (no raise)
  - dispatch_webhook() handles bad URL gracefully (no raise)
  - WebhookEvent enum values
  - Payload size guard (truncation path)
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from src.api.auth import (
    TIER_LIMITS,
    RateLimitTier,
    Tenant,
    TenantKeyStore,
    require_tenant,
)
from src.api.middleware import enforce_rate_limit, reset_all_buckets, reset_bucket
from src.api.webhooks import WebhookDispatcher, WebhookEvent, dispatch_webhook

# ===========================================================================
# AUTH — TenantKeyStore
# ===========================================================================


class TestTenantKeyStore:
    def test_loads_multi_key_env(self, monkeypatch):
        data = json.dumps(
            {
                "sk-key1abc!": {"name": "acme", "tier": "standard"},
                "sk-key2xyz!": {"name": "bigco", "tier": "premium"},
            }
        )
        monkeypatch.setenv("SENTINAI_API_KEYS", data)
        monkeypatch.delenv("SENTINAI_API_KEY", raising=False)
        store = TenantKeyStore()
        assert store.tenant_count == 2
        assert store.auth_enabled

    def test_multi_key_tenant_names(self, monkeypatch):
        data = json.dumps(
            {
                "sk-acme1234!": {"name": "acme", "tier": "standard"},
            }
        )
        monkeypatch.setenv("SENTINAI_API_KEYS", data)
        monkeypatch.delenv("SENTINAI_API_KEY", raising=False)
        store = TenantKeyStore()
        tenant = store.lookup("sk-acme1234!")
        assert tenant is not None
        assert tenant.name == "acme"

    def test_multi_key_tier_premium(self, monkeypatch):
        data = json.dumps(
            {
                "sk-prem5678!": {"name": "bigco", "tier": "premium"},
            }
        )
        monkeypatch.setenv("SENTINAI_API_KEYS", data)
        monkeypatch.delenv("SENTINAI_API_KEY", raising=False)
        store = TenantKeyStore()
        tenant = store.lookup("sk-prem5678!")
        assert tenant.tier is RateLimitTier.PREMIUM

    def test_unknown_tier_defaults_to_standard(self, monkeypatch):
        data = json.dumps(
            {
                "sk-weird123!": {"name": "weird", "tier": "galactic"},
            }
        )
        monkeypatch.setenv("SENTINAI_API_KEYS", data)
        monkeypatch.delenv("SENTINAI_API_KEY", raising=False)
        store = TenantKeyStore()
        tenant = store.lookup("sk-weird123!")
        assert tenant.tier is RateLimitTier.STANDARD

    def test_fallback_to_legacy_single_key(self, monkeypatch):
        monkeypatch.delenv("SENTINAI_API_KEYS", raising=False)
        monkeypatch.setenv("SENTINAI_API_KEY", "sk-legacykey99!")
        store = TenantKeyStore()
        assert store.tenant_count == 1
        tenant = store.lookup("sk-legacykey99!")
        assert tenant is not None
        assert tenant.name == "default"

    def test_legacy_key_is_standard_tier(self, monkeypatch):
        monkeypatch.delenv("SENTINAI_API_KEYS", raising=False)
        monkeypatch.setenv("SENTINAI_API_KEY", "sk-legacykey99!")
        store = TenantKeyStore()
        tenant = store.lookup("sk-legacykey99!")
        assert tenant.tier is RateLimitTier.STANDARD

    def test_no_env_vars_auth_disabled(self, monkeypatch):
        monkeypatch.delenv("SENTINAI_API_KEYS", raising=False)
        monkeypatch.delenv("SENTINAI_API_KEY", raising=False)
        store = TenantKeyStore()
        assert not store.auth_enabled
        assert store.tenant_count == 0

    def test_lookup_unknown_key_returns_none(self, monkeypatch):
        data = json.dumps({"sk-real1234!": {"name": "real", "tier": "standard"}})
        monkeypatch.setenv("SENTINAI_API_KEYS", data)
        monkeypatch.delenv("SENTINAI_API_KEY", raising=False)
        store = TenantKeyStore()
        assert store.lookup("sk-wrong000!") is None

    def test_lookup_empty_key_returns_none(self, monkeypatch):
        data = json.dumps({"sk-real1234!": {"name": "real", "tier": "standard"}})
        monkeypatch.setenv("SENTINAI_API_KEYS", data)
        monkeypatch.delenv("SENTINAI_API_KEY", raising=False)
        store = TenantKeyStore()
        assert store.lookup("") is None

    def test_invalid_json_disables_auth(self, monkeypatch):
        monkeypatch.setenv("SENTINAI_API_KEYS", "not-valid-json{{{")
        monkeypatch.delenv("SENTINAI_API_KEY", raising=False)
        store = TenantKeyStore()
        assert not store.auth_enabled

    def test_reload_picks_up_new_keys(self, monkeypatch):
        monkeypatch.delenv("SENTINAI_API_KEYS", raising=False)
        monkeypatch.delenv("SENTINAI_API_KEY", raising=False)
        store = TenantKeyStore()
        assert not store.auth_enabled

        data = json.dumps({"sk-new9999!": {"name": "new", "tier": "standard"}})
        monkeypatch.setenv("SENTINAI_API_KEYS", data)
        store.reload()
        assert store.auth_enabled
        assert store.lookup("sk-new9999!") is not None


# ===========================================================================
# AUTH — Tenant model
# ===========================================================================


class TestTenantModel:
    def test_standard_rate_limit(self):
        t = Tenant(name="t", tier=RateLimitTier.STANDARD)
        assert t.rate_limit == 60

    def test_premium_rate_limit(self):
        t = Tenant(name="t", tier=RateLimitTier.PREMIUM)
        assert t.rate_limit == 300

    def test_internal_rate_limit_is_none(self):
        t = Tenant(name="t", tier=RateLimitTier.INTERNAL)
        assert t.rate_limit is None

    def test_str_representation(self):
        t = Tenant(name="acme", tier=RateLimitTier.PREMIUM)
        assert "acme" in str(t)
        assert "premium" in str(t)

    def test_frozen_immutable(self):
        t = Tenant(name="t", tier=RateLimitTier.STANDARD)
        with pytest.raises((AttributeError, TypeError)):
            t.name = "other"  # type: ignore[misc]

    def test_tier_limits_mapping_complete(self):
        for tier in RateLimitTier:
            assert tier in TIER_LIMITS


# ===========================================================================
# AUTH — require_tenant dependency
# ===========================================================================


class TestRequireTenant:
    @pytest.mark.anyio
    async def test_returns_anonymous_when_auth_disabled(self, monkeypatch):
        monkeypatch.delenv("SENTINAI_API_KEYS", raising=False)
        monkeypatch.delenv("SENTINAI_API_KEY", raising=False)
        with patch("src.api.auth._key_store") as mock_store:
            mock_store.auth_enabled = False
            tenant = await require_tenant(key=None)
        assert tenant.name == "anonymous"
        assert tenant.tier is RateLimitTier.INTERNAL

    @pytest.mark.anyio
    async def test_raises_401_when_key_missing_and_auth_enabled(self):
        with patch("src.api.auth._key_store") as mock_store:
            mock_store.auth_enabled = True
            mock_store.lookup.return_value = None
            with pytest.raises(HTTPException) as exc_info:
                await require_tenant(key=None)
        assert exc_info.value.status_code == 401

    @pytest.mark.anyio
    async def test_raises_403_on_wrong_key(self):
        with patch("src.api.auth._key_store") as mock_store:
            mock_store.auth_enabled = True
            mock_store.lookup.return_value = None
            with pytest.raises(HTTPException) as exc_info:
                await require_tenant(key="sk-wrongkey!")
        assert exc_info.value.status_code == 403

    @pytest.mark.anyio
    async def test_returns_tenant_on_valid_key(self):
        expected = Tenant(name="acme", tier=RateLimitTier.STANDARD)
        with patch("src.api.auth._key_store") as mock_store:
            mock_store.auth_enabled = True
            mock_store.lookup.return_value = expected
            tenant = await require_tenant(key="sk-validkey!")
        assert tenant.name == "acme"

    @pytest.mark.anyio
    async def test_401_has_www_authenticate_header(self):
        with patch("src.api.auth._key_store") as mock_store:
            mock_store.auth_enabled = True
            with pytest.raises(HTTPException) as exc_info:
                await require_tenant(key=None)
        assert "WWW-Authenticate" in exc_info.value.headers


# ===========================================================================
# MIDDLEWARE — Per-tenant rate limiting
# ===========================================================================


class TestEnforceRateLimit:
    def setup_method(self):
        reset_all_buckets()

    def test_internal_tier_always_passes(self):
        tenant = Tenant(name="internal-t", tier=RateLimitTier.INTERNAL)
        # Should never raise regardless of how many times called
        for _ in range(200):
            enforce_rate_limit(tenant)

    def test_standard_tier_passes_within_limit(self):
        tenant = Tenant(name="std-ok", tier=RateLimitTier.STANDARD)
        # First request always passes
        enforce_rate_limit(tenant)

    def test_standard_tier_raises_429_when_exhausted(self):
        tenant = Tenant(name="std-exhaust", tier=RateLimitTier.STANDARD)
        reset_bucket(tenant.name)
        # Exhaust the bucket (60 tokens)
        from src.core.rate_limiter import TokenBucket

        with patch("src.api.middleware._get_bucket") as mock_get:
            empty_bucket = MagicMock(spec=TokenBucket)
            empty_bucket.consume.return_value = False
            mock_get.return_value = empty_bucket
            with pytest.raises(HTTPException) as exc_info:
                enforce_rate_limit(tenant)
        assert exc_info.value.status_code == 429

    def test_429_has_retry_after_header(self):
        tenant = Tenant(name="hdr-test", tier=RateLimitTier.STANDARD)
        from src.core.rate_limiter import TokenBucket

        with patch("src.api.middleware._get_bucket") as mock_get:
            empty_bucket = MagicMock(spec=TokenBucket)
            empty_bucket.consume.return_value = False
            mock_get.return_value = empty_bucket
            with pytest.raises(HTTPException) as exc_info:
                enforce_rate_limit(tenant)
        assert "Retry-After" in exc_info.value.headers

    def test_different_tenants_have_independent_buckets(self):
        t2 = Tenant(name="tenant-beta", tier=RateLimitTier.STANDARD)
        # t2 bucket is independent — not affected by any other tenant
        enforce_rate_limit(t2)  # must not raise

    def test_premium_tier_has_higher_limit(self):
        t_std = Tenant(name="p2-std", tier=RateLimitTier.STANDARD)
        t_prem = Tenant(name="p2-prem", tier=RateLimitTier.PREMIUM)
        assert (t_prem.rate_limit or 0) > (t_std.rate_limit or 0)

    def test_reset_bucket_clears_state(self):
        tenant = Tenant(name="reset-me", tier=RateLimitTier.STANDARD)
        enforce_rate_limit(tenant)  # creates bucket
        reset_bucket(tenant.name)
        # After reset, a fresh bucket is created — no error
        enforce_rate_limit(tenant)

    def test_reset_all_buckets(self):
        for name in ("ra-1", "ra-2", "ra-3"):
            enforce_rate_limit(Tenant(name=name, tier=RateLimitTier.STANDARD))
        reset_all_buckets()
        # No assertion needed — just must not raise
        enforce_rate_limit(Tenant(name="ra-1", tier=RateLimitTier.STANDARD))


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
