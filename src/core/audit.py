"""Immutable audit logger (A4).

Every AI action produces a structured JSON log entry that is:
- Appended to logs/sentinai-audit.jsonl (one JSON object per line)
- Also stored in the audit_events table when a session factory is given, so
  history survives redeploys (the log file does not on Render)
- Never modified or deleted by the system
- Queryable by incident_id

Reads prefer the database and fall back to the file when the database is empty
or unreachable. A database failure never breaks the pipeline.

Log schema
----------
{
  "timestamp":       "2026-05-12T10:00:00.000+00:00",
  "incident_id":     "abc123",
  "model":           "claude-sonnet-4-20250514",
  "provider":        "anthropic",
  "patch_file":      "src/services/handler.py",
  "patch_hash":      "sha256:...",
  "policy_decision": "allow",
  "risk_tier":       "low",
  "review_required": false,
  "patch_applied":   true,
  "tests_passed":    true,
  "pr_url":          "https://github.com/...",
  "failure_reason":  null,
  "confidence":      0.82,
  "source":          "provider"
}
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import AuditEvent
from src.db.session import SessionLocal

logger = logging.getLogger(__name__)

_DEFAULT_AUDIT_LOG = Path("logs/sentinai-audit.jsonl")
_write_lock = threading.Lock()

SessionFactory = Callable[[], Session]


def _sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def _iso(value: datetime) -> str:
    """UTC ISO string with milliseconds, identical to what the file stores."""
    if value.tzinfo is None:
        # SQLite does not store time zones and returns naive values; they are UTC.
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat(timespec="milliseconds")


def _to_dict(row: AuditEvent) -> dict:
    return {
        "timestamp": _iso(row.timestamp),
        "incident_id": row.incident_id,
        "model": row.model,
        "provider": row.provider,
        "patch_file": row.patch_file,
        "patch_hash": row.patch_hash,
        "policy_decision": row.policy_decision,
        "risk_tier": row.risk_tier,
        "review_required": row.review_required,
        "patch_applied": row.patch_applied,
        "tests_passed": row.tests_passed,
        "pr_url": row.pr_url,
        "failure_reason": row.failure_reason,
        "confidence": row.confidence,
        "source": row.source,
    }


class AuditLogger:
    """Write immutable audit entries for every pipeline action.

    Parameters
    ----------
    log_path:
        Path to the .jsonl file. Created (with parent dirs) if absent.
    session_factory:
        Optional SQLAlchemy session factory. When given, entries are also
        stored in the audit_events table and reads prefer it.
    """

    def __init__(
        self,
        log_path: Path = _DEFAULT_AUDIT_LOG,
        session_factory: SessionFactory | None = None,
    ) -> None:
        self._path = log_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._session_factory = session_factory

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        *,
        incident_id: str,
        model: str,
        provider: str,
        patch_file: str | None,
        patch: str | None,
        policy_decision: str | None,
        risk_tier: str | None,
        review_required: bool,
        patch_applied: bool,
        tests_passed: bool | None,
        pr_url: str | None,
        failure_reason: str | None,
        confidence: float,
        source: str,
    ) -> dict:
        """Build and append one audit entry. Returns the entry dict."""
        now = datetime.now(UTC)
        entry: dict = {
            "timestamp": _iso(now),
            "incident_id": incident_id,
            "model": model,
            "provider": provider,
            "patch_file": patch_file,
            "patch_hash": _sha256(patch) if patch else None,
            "policy_decision": policy_decision,
            "risk_tier": risk_tier,
            "review_required": review_required,
            "patch_applied": patch_applied,
            "tests_passed": tests_passed,
            "pr_url": pr_url,
            "failure_reason": failure_reason,
            "confidence": round(confidence, 4),
            "source": source,
        }
        self._append(entry)
        self._store(entry, now)
        return entry

    def tail(self, n: int = 50) -> list[dict]:
        """Return the last n audit entries (most recent last)."""
        rows = self._db_tail(n)
        if rows:
            return rows
        return self._file_tail(n)

    def find(self, incident_id: str) -> list[dict]:
        """Return all audit entries for a given incident_id."""
        rows = self._db_find(incident_id)
        if rows:
            return rows
        return [e for e in self._file_tail(10_000) if e.get("incident_id") == incident_id]

    # ------------------------------------------------------------------
    # File storage
    # ------------------------------------------------------------------

    def _append(self, entry: dict) -> None:
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with _write_lock:
            try:
                with self._path.open("a", encoding="utf-8") as fh:
                    fh.write(line)
            except OSError as exc:
                logger.error("Audit write failed: %s", exc)

    def _file_tail(self, n: int) -> list[dict]:
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                lines = list(deque(fh, maxlen=n))
        except FileNotFoundError:
            return []
        entries = []
        for line in lines:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return entries

    # ------------------------------------------------------------------
    # Database storage
    # ------------------------------------------------------------------

    def _store(self, entry: dict, when: datetime) -> None:
        if self._session_factory is None:
            return
        try:
            with self._session_factory() as db:
                db.add(AuditEvent(**{**entry, "timestamp": when}))
                db.commit()
        except Exception as exc:
            logger.error("Audit database write failed: %s", exc)

    def _db_tail(self, n: int) -> list[dict]:
        if self._session_factory is None:
            return []
        try:
            with self._session_factory() as db:
                stmt = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(n)
                rows = db.execute(stmt).scalars().all()
                return [_to_dict(row) for row in reversed(rows)]
        except Exception as exc:
            logger.warning("Audit database read failed, using file: %s", exc)
            return []

    def _db_find(self, incident_id: str) -> list[dict]:
        if self._session_factory is None:
            return []
        try:
            with self._session_factory() as db:
                stmt = (
                    select(AuditEvent)
                    .where(AuditEvent.incident_id == incident_id)
                    .order_by(AuditEvent.id.asc())
                )
                return [_to_dict(row) for row in db.execute(stmt).scalars().all()]
        except Exception as exc:
            logger.warning("Audit database read failed, using file: %s", exc)
            return []


# Module-level singleton: import and use directly
audit_logger = AuditLogger(session_factory=SessionLocal)
