"""Tests for the database-backed audit log."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.audit import AuditLogger
from src.db.models import Base


def _factory(tmp_path: Path) -> sessionmaker:
    engine = create_engine(f"sqlite:///{tmp_path / 'audit.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _broken_factory():
    raise RuntimeError("database down")


def _record(log: AuditLogger, incident_id: str = "inc-1") -> dict:
    return log.record(
        incident_id=incident_id,
        model="m",
        provider="p",
        patch_file="src/x.py",
        patch="-a\n+b\n",
        policy_decision="allow",
        risk_tier="low",
        review_required=False,
        patch_applied=True,
        tests_passed=True,
        pr_url=None,
        failure_reason=None,
        confidence=0.82,
        source="provider",
    )


def test_entry_is_stored_in_database_and_matches_file_entry(tmp_path: Path) -> None:
    log_path = tmp_path / "audit.jsonl"
    log = AuditLogger(log_path=log_path, session_factory=_factory(tmp_path))
    entry = _record(log)
    assert log_path.exists()
    log_path.unlink()  # prove the next read comes from the database
    assert log.tail() == [entry]


def test_tail_is_oldest_first_and_limited(tmp_path: Path) -> None:
    log = AuditLogger(log_path=tmp_path / "a.jsonl", session_factory=_factory(tmp_path))
    for i in range(5):
        _record(log, incident_id=f"i{i}")
    assert [e["incident_id"] for e in log.tail(3)] == ["i2", "i3", "i4"]


def test_find_filters_by_incident(tmp_path: Path) -> None:
    log = AuditLogger(log_path=tmp_path / "a.jsonl", session_factory=_factory(tmp_path))
    _record(log, "a")
    _record(log, "b")
    _record(log, "a")
    assert len(log.find("a")) == 2
    assert log.find("missing") == []


def test_database_failure_does_not_break_recording(tmp_path: Path) -> None:
    log = AuditLogger(log_path=tmp_path / "a.jsonl", session_factory=_broken_factory)
    entry = _record(log)
    assert log.tail() == [entry]
    assert log.find("inc-1") == [entry]


def test_empty_database_falls_back_to_file(tmp_path: Path) -> None:
    log_path = tmp_path / "a.jsonl"
    entry = _record(AuditLogger(log_path=log_path))
    reader = AuditLogger(log_path=log_path, session_factory=_factory(tmp_path))
    assert reader.tail() == [entry]
