"""The scan path writes one audit entry per detected incident."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from src.core.audit import AuditLogger
from src.core.state import AppState
from src.models.events import LogIncident, RemediationSuggestion


def _incident() -> LogIncident:
    return LogIncident(
        incident_id="inc-1",
        detected_at_utc=datetime.now(UTC),
        trigger_line="ERROR boom",
        stacktrace="ERROR boom",
    )


def _suggestion(**kwargs) -> RemediationSuggestion:
    base = dict(
        summary="s",
        proposed_code_fix="",
        proposed_config_change="",
        confidence=0.5,
        risks="",
    )
    base.update(kwargs)
    return RemediationSuggestion(**base)


def test_record_audit_writes_entry(tmp_path: Path) -> None:
    state = AppState(audit=AuditLogger(log_path=tmp_path / "audit.jsonl"))
    state._record_audit(_incident(), _suggestion(awaiting_approval=True))
    entries = state.audit.tail()
    assert len(entries) == 1
    assert entries[0]["incident_id"] == "inc-1"
    assert entries[0]["source"] == "stub"
    assert entries[0]["review_required"] is True
    assert entries[0]["patch_applied"] is False


def test_pr_url_marks_patch_applied(tmp_path: Path) -> None:
    state = AppState(audit=AuditLogger(log_path=tmp_path / "audit.jsonl"))
    state._record_audit(_incident(), _suggestion(pr_url="https://github.com/o/r/pull/1"))
    entry = state.audit.tail()[0]
    assert entry["patch_applied"] is True
    assert entry["pr_url"] == "https://github.com/o/r/pull/1"


class _BrokenAudit:
    def record(self, **kwargs):
        raise RuntimeError("audit down")


def test_audit_failure_never_breaks_scan_path() -> None:
    state = AppState(audit=_BrokenAudit())
    state._record_audit(_incident(), _suggestion())  # must not raise
