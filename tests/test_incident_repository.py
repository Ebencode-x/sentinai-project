"""Incident and suggestion storage: dedupe by fingerprint, ordering and round trips."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from src.db import repository
from src.db.models import Account, Incident
from src.models.events import LogIncident, RemediationSuggestion


def _incident(fingerprint: str = "fp-1", at: datetime | None = None) -> LogIncident:
    return LogIncident(
        incident_id=fingerprint,
        detected_at_utc=at or datetime.now(UTC),
        trigger_line="ValueError: boom",
        stacktrace="Traceback (most recent call last):",
    )


def _suggestion(summary: str = "fix", **extra) -> RemediationSuggestion:
    return RemediationSuggestion(
        summary=summary,
        proposed_code_fix="c",
        proposed_config_change="x",
        confidence=0.7,
        risks="low",
        **extra,
    )


def test_a_new_incident_is_stored_and_a_repeat_is_only_counted(app_db):
    factory, account_id = app_db
    with factory() as db:
        first = repository.insert_incident_if_new(db, account_id, _incident())
        again = repository.insert_incident_if_new(db, account_id, _incident())
        row = db.scalars(select(Incident)).one()
    assert first is not None
    assert again is None
    assert row.occurrence_count == 2


def test_the_default_account_is_the_oldest_one(app_db):
    factory, account_id = app_db
    with factory() as db:
        db.add(Account(name="newer"))
        db.commit()
        assert repository.default_account_id(db) == account_id


def test_two_accounts_keep_separate_incidents(app_db):
    factory, account_id = app_db
    with factory() as db:
        other = Account(name="other")
        db.add(other)
        db.commit()
        assert repository.insert_incident_if_new(db, account_id, _incident()) is not None
        assert repository.insert_incident_if_new(db, other.id, _incident()) is not None
        assert len(repository.list_incidents(db, account_id, 10)) == 1
        assert len(repository.list_incidents(db, other.id, 10)) == 1


def test_incidents_come_back_oldest_first_and_limited(app_db):
    factory, account_id = app_db
    base = datetime.now(UTC)
    with factory() as db:
        for i in range(5):
            repository.insert_incident_if_new(
                db, account_id, _incident(f"fp-{i}", base + timedelta(seconds=i))
            )
        got = repository.list_incidents(db, account_id, 3)
    assert [i.incident_id for i in got] == ["fp-2", "fp-3", "fp-4"]


def test_a_suggestion_round_trip_keeps_the_optional_fields(app_db):
    factory, account_id = app_db
    suggestion = _suggestion(
        "fix",
        proposed_patch="-a\n+b\n",
        pr_url="https://example.com/pull/1",
        pr_number=1,
        patch_file="src/x.py",
        before_sha="abc123",
        branch_name="sentinai/fix",
        awaiting_approval=True,
        source="provider",
        model="m",
    )
    with factory() as db:
        pk = repository.insert_incident_if_new(db, account_id, _incident())
        repository.add_suggestion(db, account_id, pk, suggestion)
        got = repository.latest_suggestion(db, account_id)
    assert got is not None
    assert got.id == suggestion.id
    assert got.pr_number == 1
    assert got.patch_file == "src/x.py"
    assert got.awaiting_approval is True
    assert got.source == "provider"


def test_counts_are_grouped_by_source(app_db):
    factory, account_id = app_db
    with factory() as db:
        pk = repository.insert_incident_if_new(db, account_id, _incident())
        repository.add_suggestion(db, account_id, pk, _suggestion("a"))
        repository.add_suggestion(db, account_id, pk, _suggestion("b"))
        repository.add_suggestion(db, account_id, pk, _suggestion("c", source="provider"))
        found = repository.counts(db, account_id)
    assert found["incidents"] == 1
    assert found["suggestions"] == 3
    assert found["by_source"] == {"stub": 2, "provider": 1}
