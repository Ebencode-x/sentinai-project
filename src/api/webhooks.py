"""Phase 2 — Webhook dispatcher.

Sends JSON POST requests to registered webhook URLs after key pipeline
events: incident detected, suggestion generated, patch applied.

Configuration
-------------
Set SENTINAI_WEBHOOK_URLS as a comma-separated list of URLs:

    SENTINAI_WEBHOOK_URLS=https://hooks.example.com/sentinai,https://...

Delivery guarantees
-------------------
Best-effort: one attempt per event, 5-second timeout.
Failed deliveries are logged as WARNING — they do not affect the pipeline.
Retries and queuing are out of scope for MVP (add a task queue in Phase 3).

Payload schema
--------------
{
    "event":      "incident.detected" | "suggestion.generated" | "patch.applied",
    "timestamp":  "2026-05-16T10:00:00Z",   # ISO-8601 UTC
    "payload":    { ...event-specific data }
}
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)

_ENV_URLS = "SENTINAI_WEBHOOK_URLS"
_TIMEOUT_SECONDS = 5
_MAX_PAYLOAD_BYTES = 512 * 1024  # 512 KB guard


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------


class WebhookEvent(StrEnum):
    INCIDENT_DETECTED = "incident.detected"
    SUGGESTION_GENERATED = "suggestion.generated"
    PATCH_APPLIED = "patch.applied"
    INJECTION_BLOCKED = "injection.blocked"
    POLICY_BLOCKED = "policy.blocked"


# ---------------------------------------------------------------------------
# URL registry
# ---------------------------------------------------------------------------


def _load_urls() -> list[str]:
    """Read and validate webhook URLs from environment."""
    raw = os.getenv(_ENV_URLS, "")
    if not raw.strip():
        return []
    urls = [u.strip() for u in raw.split(",") if u.strip()]
    valid = []
    for url in urls:
        if url.startswith(("http://", "https://")):
            valid.append(url)
        else:
            logger.warning("[Webhook] Ignoring invalid URL (must start with http/https): %r", url)
    return valid


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


class WebhookDispatcher:
    """Stateless dispatcher — safe to share across threads.

    Reloads URLs on every dispatch call so env changes are picked up
    without a restart (suitable for MVP; cache in Phase 3 if needed).
    """

    def dispatch(
        self,
        event: WebhookEvent,
        payload: dict[str, Any],
    ) -> list[str]:
        """Send *payload* to all registered webhook URLs.

        Returns a list of URLs that succeeded.
        Failed deliveries are logged but never raise.
        """
        urls = _load_urls()
        if not urls:
            logger.debug("[Webhook] No URLs configured — skipping dispatch for %s", event)
            return []

        body = self._build_body(event, payload)
        body_bytes = json.dumps(body, default=str).encode()

        if len(body_bytes) > _MAX_PAYLOAD_BYTES:
            logger.warning(
                "[Webhook] Payload for %s exceeds %d KB — truncating description fields",
                event,
                _MAX_PAYLOAD_BYTES // 1024,
            )
            body_bytes = json.dumps(
                self._build_body(event, {"truncated": True, "event": str(event)}),
                default=str,
            ).encode()

        succeeded: list[str] = []
        for url in urls:
            if self._post(url, body_bytes):
                succeeded.append(url)

        return succeeded

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_body(event: WebhookEvent, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "event": str(event),
            "timestamp": datetime.now(UTC).isoformat(),
            "payload": payload,
        }

    @staticmethod
    def _post(url: str, body_bytes: bytes) -> bool:
        """HTTP POST body_bytes to url.  Returns True on 2xx response."""
        # Scheme validation — only http/https are permitted.
        # _load_urls() already enforces this; this is defense-in-depth.
        if not url.startswith(("http://", "https://")):
            logger.warning("[Webhook] Refusing to POST to non-http(s) URL: %r", url)
            return False

        req = urllib.request.Request(
            url,
            data=body_bytes,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "User-Agent": "SentinAI-Webhook/1.0",
            },
        )
        try:
            # nosec B310 — URL scheme validated above; only http/https reach this line
            with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:  # nosec B310
                status_code = resp.status
                if 200 <= status_code < 300:
                    logger.info("[Webhook] Delivered to %s (%d)", url, status_code)
                    return True
                logger.warning("[Webhook] Non-2xx response from %s: %d", url, status_code)
                return False
        except urllib.error.HTTPError as exc:
            logger.warning("[Webhook] HTTP error posting to %s: %s", url, exc)
        except urllib.error.URLError as exc:
            logger.warning("[Webhook] URL error posting to %s: %s", url, exc)
        except TimeoutError:
            logger.warning("[Webhook] Timeout posting to %s (>%ds)", url, _TIMEOUT_SECONDS)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[Webhook] Unexpected error posting to %s: %s", url, exc)
        return False


# Module-level singleton
_dispatcher = WebhookDispatcher()


def dispatch_webhook(event: WebhookEvent, payload: dict[str, Any]) -> list[str]:
    """Convenience wrapper around the module singleton."""
    return _dispatcher.dispatch(event, payload)
