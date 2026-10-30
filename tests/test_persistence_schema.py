"""The incident persistence tables: they match the models and enforce the rules the app needs."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, delete, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from src.db.migrate import run_migrations
from src.db.models import Account, Base, Incident, Suggestion

NEW_TABLES = {
    "incidents",
    "suggestions",
    "rollback_ledger",
    "account_settings",
    "notification_channels",
}


@pytest.fixture
def db(pg_url):
    run_migrations(pg_url)
    engine = create_engine(pg_url)
    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        yield session
    engine.dispose()


def _incident(account_id: str, fingerprint: str = "fp-1") -> Incident:
    now = datetime.now(UTC)
    return Incident(
        account_id=account_id,
        fingerprint=fingerprint,
        detected_at=now,
        last_seen_at=now,
        trigger_line="ValueError: boom",
        stacktrace="Traceback (most recent call last):",
    )


def _suggestion(account_id: str, incident_pk: str) -> Suggestion:
    return Suggestion(
        account_id=account_id,
        incident_pk=incident_pk,
        summary="s",
        proposed_code_fix="c",
        proposed_config_change="x",
        confidence=0.5,
        risks="r",
    )


def test_migration_creates_the_tables(pg_url):
    run_migrations(pg_url)
    engine = create_engine(pg_url)
    try:
        assert NEW_TABLES <= set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def _only_new_tables(obj, name, type_, reflected, compare_to):
    if type_ == "table":
        return name in NEW_TABLES
    table = getattr(obj, "table", None)
    return table is None or table.name in NEW_TABLES


def test_models_match_the_migration(pg_url):
    run_migrations(pg_url)
    engine = create_engine(pg_url)
    try:
        with engine.connect() as conn:
            context = MigrationContext.configure(
                conn, opts={"include_object": _only_new_tables, "compare_type": False}
            )
            assert compare_metadata(context, Base.metadata) == []
    finally:
        engine.dispose()


def test_same_fingerprint_twice_in_one_account_is_rejected(db):
    account = Account(name="a")
    db.add(account)
    db.commit()
    db.add(_incident(account.id))
    db.commit()
    db.add(_incident(account.id))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_same_fingerprint_in_two_accounts_is_allowed(db):
    first, second = Account(name="a"), Account(name="b")
    db.add_all([first, second])
    db.commit()
    db.add_all([_incident(first.id), _incident(second.id)])
    db.commit()
    assert db.query(Incident).count() == 2


def test_deleting_an_incident_removes_its_suggestions(db):
    account = Account(name="a")
    db.add(account)
    db.commit()
    incident = _incident(account.id)
    db.add(incident)
    db.commit()
    db.add(_suggestion(account.id, incident.id))
    db.commit()
    db.execute(delete(Incident).where(Incident.id == incident.id))
    db.commit()
    assert db.query(Suggestion).count() == 0
