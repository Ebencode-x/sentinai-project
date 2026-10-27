"""Audit feed API: GET /api/audit plus archive, restore and delete.

Reads the audit log, collapses repeated entries and turns each record into a
readable event for the dashboard. Admins can archive events (hidden but kept),
restore them, and permanently delete events that are already archived.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.api.deps import require_role, require_user
from src.core.audit import audit_logger
from src.db.models import Role, User

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/audit",
    tags=["audit"],
    dependencies=[Depends(require_user)],
)

require_admin = require_role(Role.ADMIN)

# How many raw lines to scan before collapsing duplicates.
_SCAN_WINDOW = 5000
_MAX_IDS = 500


class EventIds(BaseModel):
    ids: list[int]


def _check_ids(ids: list[int]) -> None:
    if not ids or len(ids) > _MAX_IDS:
        raise HTTPException(
            status_code=422,
            detail=f"Send between 1 and {_MAX_IDS} ids.",
        )


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
        row_id = entry.get("row_id")
        if key in seen:
            seen[key]["count"] += 1
            if row_id is not None:
                seen[key]["row_ids"].append(row_id)
            continue
        title, level, detail = _classify(entry)
        raw_id = f"{key}{entry.get('timestamp')}"
        seen[key] = {
            "id": hashlib.sha1(raw_id.encode(), usedforsecurity=False).hexdigest()[:12],
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
            "model": entry.get("model"),
            "row_ids": [row_id] if row_id is not None else [],
            "archived_at": entry.get("archived_at"),
            "archived_by": entry.get("archived_by"),
            "count": 1,
        }
    return list(seen.values())[:limit]


@router.get("")
def audit_feed(
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    archived: bool = False,
) -> list[dict[str, Any]]:
    entries = audit_logger.tail_rows(_SCAN_WINDOW, archived=archived)
    return build_feed(entries, limit)


@router.post("/archive")
def archive_events(
    body: EventIds,
    user: Annotated[User, Depends(require_admin)],
) -> dict[str, int]:
    _check_ids(body.ids)
    changed = audit_logger.archive(body.ids, user.email)
    logger.info("audit: %s archived %d event(s)", user.email, changed)
    return {"changed": changed}


@router.post("/restore")
def restore_events(
    body: EventIds,
    user: Annotated[User, Depends(require_admin)],
) -> dict[str, int]:
    _check_ids(body.ids)
    changed = audit_logger.restore(body.ids)
    logger.info("audit: %s restored %d event(s)", user.email, changed)
    return {"changed": changed}


@router.post("/delete")
def delete_events(
    body: EventIds,
    user: Annotated[User, Depends(require_admin)],
) -> dict[str, int]:
    """Permanently delete events. Only events that are already archived qualify."""
    _check_ids(body.ids)
    changed = audit_logger.delete_archived(body.ids)
    logger.warning("audit: %s permanently deleted %d event(s)", user.email, changed)
    return {"changed": changed}
