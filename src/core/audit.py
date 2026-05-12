"""Immutable audit logger — A4.

Every AI action produces a structured JSON log entry that is:
- Written atomically to logs/sentinai-audit.jsonl (one JSON object per line)
- Never modified or deleted by the system
- Queryable by incident_id, model, risk_tier, decision

Log schema
----------
{
  "timestamp":       "2026-05-12T10:00:00.000Z",
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
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_AUDIT_LOG = Path("logs/sentinai-audit.jsonl")
_write_lock = threading.Lock()


def _sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


class AuditLogger:
    """Write immutable JSONL audit entries for every pipeline action.

    Parameters
    ----------
    log_path:
        Path to the .jsonl file. Created (with parent dirs) if absent.
    """

    def __init__(self, log_path: Path = _DEFAULT_AUDIT_LOG) -> None:
        self._path = log_path
        self._path.parent.mkdir(parents=True, exist_ok=True)

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
        entry: dict = {
            "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
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
        return entry

    def tail(self, n: int = 50) -> list[dict]:
        """Return the last n audit entries (most recent last)."""
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
            entries = []
            for line in lines[-n:]:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            return entries
        except FileNotFoundError:
            return []

    def find(self, incident_id: str) -> list[dict]:
        """Return all audit entries for a given incident_id."""
        return [e for e in self.tail(n=10_000) if e.get("incident_id") == incident_id]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _append(self, entry: dict) -> None:
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with _write_lock:
            try:
                with self._path.open("a", encoding="utf-8") as fh:
                    fh.write(line)
            except OSError as exc:
                logger.error("Audit write failed: %s", exc)


# Module-level singleton — import and use directly
audit_logger = AuditLogger()
