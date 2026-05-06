"""Outbound notification layer for SentinAI (Milestone 3).

Routing logic:
  critical severity  -> Slack webhook  +  generic HTTP webhook  (immediately)
  warning severity   -> Slack webhook only
  confidence < 0.5   -> payload flagged as low-confidence
  source == fallback -> payload flagged as provider-degraded

Environment variables
---------------------
SENTINAI_SLACK_WEBHOOK_URL   Incoming Webhook URL from a Slack app.
SENTINAI_GENERIC_WEBHOOK_URL Any HTTP endpoint that accepts a POST with JSON.
NOTIFICATION_TIMEOUT_SECONDS Per-request timeout (default 8).
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from src.models.events import LogIncident, RemediationSuggestion

logger = logging.getLogger(__name__)

SLACK_WEBHOOK_URL: str = os.getenv("SENTINAI_SLACK_WEBHOOK_URL", "")
GENERIC_WEBHOOK_URL: str = os.getenv("SENTINAI_GENERIC_WEBHOOK_URL", "")
NOTIFICATION_TIMEOUT: float = float(os.getenv("NOTIFICATION_TIMEOUT_SECONDS", "8"))


def notify(incident: LogIncident, suggestion: RemediationSuggestion) -> None:
    """Fire notifications for a new incident/suggestion pair.

    critical -> Slack + generic webhook
    warning  -> Slack only
    Errors are logged but never raised.
    """
    if incident.severity == "critical":
        _send_slack(incident, suggestion)
        _send_generic_webhook(incident, suggestion)
    else:
        _send_slack(incident, suggestion)


def _send_slack(incident: LogIncident, suggestion: RemediationSuggestion) -> None:
    if not SLACK_WEBHOOK_URL:
        return
    payload = _build_slack_payload(incident, suggestion)
    try:
        with httpx.Client(timeout=NOTIFICATION_TIMEOUT) as client:
            response = client.post(SLACK_WEBHOOK_URL, json=payload)
        if not response.is_success:
            logger.warning("Slack notification failed [%s]: %s", response.status_code, response.text[:200])
        else:
            logger.debug("Slack notification sent for incident %s", incident.incident_id)
    except Exception as exc:
        logger.warning("Slack notification error for incident %s: %s", incident.incident_id, exc)


def _build_slack_payload(incident: LogIncident, suggestion: RemediationSuggestion) -> dict[str, Any]:
    severity_emoji = "🔴" if incident.severity == "critical" else "🟡"
    severity_label = incident.severity.upper()

    conf = suggestion.confidence
    filled = round(conf * 10)
    conf_bar = "█" * filled + "░" * (10 - filled)
    conf_pct = f"{conf * 100:.0f}%"

    flags: list[str] = []
    if conf < 0.5:
        flags.append("⚠️ *Low confidence* — human review recommended")
    if suggestion.source == "fallback":
        flags.append("🔴 *Provider degraded* — heuristic fallback used")

    patch_preview = ""
    if suggestion.proposed_patch:
        lines = suggestion.proposed_patch.strip().splitlines()
        preview_lines = lines[:6]
        patch_preview = "\n".join(preview_lines)
        if len(lines) > 6:
            patch_preview += f"\n… (+{len(lines) - 6} more lines)"

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{severity_emoji} {severity_label} — SentinAI Alert", "emoji": True},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Incident ID*\n`{incident.incident_id}`"},
                {"type": "mrkdwn", "text": f"*Detected*\n{incident.detected_at_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC"},
                {"type": "mrkdwn", "text": f"*Trigger*\n```{incident.trigger_line[:120]}```"},
                {"type": "mrkdwn", "text": f"*LLM Source*\n`{suggestion.source}`"},
            ],
        },
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Summary*\n{suggestion.summary}"}},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Proposed Fix*\n{suggestion.proposed_code_fix[:280]}{'…' if len(suggestion.proposed_code_fix) > 280 else ''}",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Confidence*\n`{conf_bar}` {conf_pct}"},
                {"type": "mrkdwn", "text": f"*Risks*\n{suggestion.risks[:200]}"},
            ],
        },
    ]

    if flags:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(flags)}})

    if patch_preview:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*Patch Preview*\n```{patch_preview}```"}})

    if suggestion.test_guidance:
        blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": f"🧪 *Test guidance:* {suggestion.test_guidance[:200]}"}]})

    blocks.append({"type": "divider"})
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": "Sent by *SentinAI* · Self-Healing DevOps Agent"}]})

    return {"blocks": blocks}


def _send_generic_webhook(incident: LogIncident, suggestion: RemediationSuggestion) -> None:
    if not GENERIC_WEBHOOK_URL:
        return
    payload = _build_generic_payload(incident, suggestion)
    try:
        with httpx.Client(timeout=NOTIFICATION_TIMEOUT) as client:
            response = client.post(GENERIC_WEBHOOK_URL, json=payload, headers={"Content-Type": "application/json", "User-Agent": "SentinAI/1.0"})
        if not response.is_success:
            logger.warning("Generic webhook failed [%s]: %s", response.status_code, response.text[:200])
        else:
            logger.debug("Generic webhook sent for incident %s", incident.incident_id)
    except Exception as exc:
        logger.warning("Generic webhook error for incident %s: %s", incident.incident_id, exc)


def _build_generic_payload(incident: LogIncident, suggestion: RemediationSuggestion) -> dict[str, Any]:
    flags: list[str] = []
    if suggestion.confidence < 0.5:
        flags.append("low_confidence")
    if suggestion.source == "fallback":
        flags.append("provider_degraded")

    return {
        "event": "sentinai.incident.detected",
        "schema_version": "1.0",
        "incident": {
            "id": incident.incident_id,
            "detected_at_utc": incident.detected_at_utc.isoformat(),
            "severity": incident.severity,
            "trigger_line": incident.trigger_line,
            "stacktrace_preview": incident.stacktrace[:500],
        },
        "suggestion": {
            "source": suggestion.source,
            "confidence": suggestion.confidence,
            "summary": suggestion.summary,
            "proposed_code_fix": suggestion.proposed_code_fix,
            "proposed_config_change": suggestion.proposed_config_change,
            "risks": suggestion.risks,
            "proposed_patch": suggestion.proposed_patch,
            "test_guidance": suggestion.test_guidance,
            "provider_error": suggestion.provider_error,
        },
        "flags": flags,
    }
