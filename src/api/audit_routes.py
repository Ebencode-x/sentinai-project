"""Audit feed API: GET /api/audit.

Reads the append-only audit log, collapses repeated entries and turns each
record into a readable event for the dashboard.
"""

from __future__ import annotations

import hashlib
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from src.api.deps import require_user
from src.core.audit import audit_logger

router = APIRouter(
    prefix="/audit",
    tags=["audit"],
    dependencies=[Depends(require_user)],
)

# How many raw lines to scan before collapsing duplicates.
_SCAN_WINDOW = 5000


def _classify(entry: dict[str, Any]) -> tuple[str, str, str]:
    """Return (title, level, detail) for one audit record."""
    decision = (entry.get("policy_decision") or "").lower()
    reason = entry.get("failure_reason")
    if decision in {"deny", "block", "blocked"}:
        return "Policy denied the patch", "danger", reason or ""
    if entry.get("patch_applied"):
        if entry.get("pr_url"):
            return "Patch applied, pull request opened", "success", ""
        return "Patch applied", "success", ""
    if reason:
        return "Patch not applied", "warning", reason
    if entry.get("review_required"):
        return "Waiting for review", "warning", ""
    return "Suggestion recorded", "info", ""


def build_feed(entries: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Newest first, repeated records collapsed into one event with a count."""
    seen: dict[tuple, dict[str, Any]] = {}
    for entry in reversed(entries):
        key = (
            entry.get("incident_id"),
            entry.get("patch_hash"),
            entry.get("failure_reason"),
        )
        if key in seen:
            seen[key]["count"] += 1
            continue
        title, level, detail = _classify(entry)
        raw_id = f"{key}{entry.get('timestamp')}"
        seen[key] = {
            "id": hashlib.sha1(raw_id.encode()).hexdigest()[:12],
            "timestamp": entry.get("timestamp"),
            "incident_id": entry.get("incident_id"),
            "title": title,
            "level": level,
            "detail": detail,
            "provider": entry.get("provider"),
            "source": entry.get("source"),
            "patch_file": entry.get("patch_file"),
            "pr_url": entry.get("pr_url"),
            "risk_tier": entry.get("risk_tier"),
            "confidence": entry.get("confidence"),
            "count": 1,
        }
    return list(seen.values())[:limit]


@router.get("")
def audit_feed(
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict[str, Any]]:
    return build_feed(audit_logger.tail(n=_SCAN_WINDOW), limit)
