"""Event sources: keys are shown once, stored hashed, and scoped to an account."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, delete, select
from sqlalchemy.exc import IntegrityError

from src.core.api_keys import generate_key, matches, prefix_of
from src.db import sources
from src.db.migrate import run_migrations
from src.db.models import Account, Base, IngestedEvent, Source

CHECKED_TABLES = {"sources", "ingest_events", "incidents"}


def _checked_only(obj, name, type_, reflected, compare_to):
    if type_ == "table":
        return name in CHECKED_TABLES
    table = getattr(obj, "table", None)
    return table is None or table.name in CHECKED_TABLES


def _event(account_id: str, source_id: str, event_id: str = "e-1") -> IngestedEvent:
    return IngestedEvent(
        account_id=account_id,
        source_id=source_id,
        event_id=event_id,
        occurred_at=datetime.now(UTC),
        message="boom",
        fingerprint="fp-1",
    )


def test_a_generated_key_is_well_formed_and_matches_only_its_own_hash():
    key, prefix, key_hash = generate_key()
    assert prefix_of(key) == prefix
    assert matches(key, key_hash)
    other, _, other_hash = generate_key()
    assert key != other
    assert not matches(key, other_hash)


@pytest.mark.parametrize("bad", [None, "", "snl_", "snl_zzzzzzzz_x", "sk-not-ours", "snl_12345678"])
def test_malformed_keys_have_no_prefix(bad):
    assert prefix_of(bad) is None


def test_a_created_key_authenticates_and_is_never_stored(app_db):
    factory, account_id = app_db
    with factory() as db:
        source, key = sources.create_source(db, account_id, "agrolink", "admin@test")
        found = sources.authenticate(db, key)
        stored = db.scalars(select(Source)).one()
    assert found is not None
    assert found.id == source.id
    assert key not in (stored.key_prefix, stored.key_hash)
    assert stored.key_prefix == prefix_of(key)


def test_wrong_unknown_and_malformed_keys_are_refused(app_db):
    factory, account_id = app_db
    with factory() as db:
        _source, key = sources.create_source(db, account_id, "agrolink")
        tampered = key[:-1] + ("A" if key[-1] != "A" else "B")
        unknown, _, _ = generate_key()
        assert sources.authenticate(db, tampered) is None
        assert sources.authenticate(db, unknown) is None
        assert sources.authenticate(db, "") is None
        assert sources.authenticate(db, None) is None


def test_a_revoked_key_stops_working_and_revoking_is_repeatable(app_db):
    factory, account_id = app_db
    with factory() as db:
        source, key = sources.create_source(db, account_id, "agrolink")
        assert sources.revoke_source(db, account_id, source.id) is True
        assert sources.revoke_source(db, account_id, source.id) is True
        assert sources.revoke_source(db, account_id, "nonexistent") is False
        assert sources.authenticate(db, key) is None


def test_rotating_replaces_the_key_at_once(app_db):
    factory, account_id = app_db
    with factory() as db:
        source, old_key = sources.create_source(db, account_id, "agrolink")
        new_key = sources.rotate_key(db, account_id, source.id)
        assert new_key and new_key != old_key
        assert sources.authenticate(db, old_key) is None
        assert sources.authenticate(db, new_key).id == source.id
        assert sources.rotate_key(db, account_id, "nonexistent") is None


def test_a_revoked_source_cannot_be_rotated_back_to_life(app_db):
    factory, account_id = app_db
    with factory() as db:
        source, _key = sources.create_source(db, account_id, "agrolink")
        sources.revoke_source(db, account_id, source.id)
        with pytest.raises(ValueError, match="revoked"):
            sources.rotate_key(db, account_id, source.id)


def test_names_are_unique_per_account_but_reusable_across_accounts(app_db):
    factory, account_id = app_db
    with factory() as db:
        other = Account(name="other")
        db.add(other)
        db.commit()
        sources.create_source(db, account_id, "agrolink")
        with pytest.raises(ValueError, match="already exists"):
            sources.create_source(db, account_id, "agrolink")
        sources.create_source(db, other.id, "agrolink")
        assert len(sources.list_sources(db, account_id)) == 1
        assert len(sources.list_sources(db, other.id)) == 1


@pytest.mark.parametrize("bad", ["", "Has Space", "UPPER", "-lead", "x" * 33, "a/b"])
def test_invalid_names_are_rejected(app_db, bad):
    factory, account_id = app_db
    with factory() as db, pytest.raises(ValueError, match="source name"):
        sources.create_source(db, account_id, bad)


def test_one_account_cannot_touch_another_accounts_source(app_db):
    factory, account_id = app_db
    with factory() as db:
        source, _key = sources.create_source(db, account_id, "agrolink")
        other = Account(name="other")
        db.add(other)
        db.commit()
        assert sources.get_source(db, other.id, source.id) is None
        assert sources.revoke_source(db, other.id, source.id) is False
        assert sources.rotate_key(db, other.id, source.id) is None


def test_last_use_is_recorded_but_not_rewritten_on_every_request(app_db):
    factory, account_id = app_db
    with factory() as db:
        _source, key = sources.create_source(db, account_id, "agrolink")
        first = sources.authenticate(db, key).last_used_at
        second = sources.authenticate(db, key).last_used_at
    assert first is not None
    assert first == second


def test_an_event_id_is_unique_per_source(app_db):
    factory, account_id = app_db
    with factory() as db:
        source, _key = sources.create_source(db, account_id, "agrolink")
        db.add(_event(account_id, source.id))
        db.commit()
        db.add(_event(account_id, source.id))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_the_same_event_id_is_allowed_for_two_sources(app_db):
    factory, account_id = app_db
    with factory() as db:
        first, _ = sources.create_source(db, account_id, "agrolink")
        second, _ = sources.create_source(db, account_id, "orders-api")
        db.add_all([_event(account_id, first.id), _event(account_id, second.id)])
        db.commit()
        assert db.query(IngestedEvent).count() == 2


def test_deleting_a_source_deletes_its_events(app_db):
    factory, account_id = app_db
    with factory() as db:
        source, _key = sources.create_source(db, account_id, "agrolink")
        db.add(_event(account_id, source.id))
        db.commit()
        db.execute(delete(Source).where(Source.id == source.id))
        db.commit()
        assert db.query(IngestedEvent).count() == 0


def test_models_match_the_migration(pg_url):
    run_migrations(pg_url)
    engine = create_engine(pg_url)
    try:
        with engine.connect() as conn:
            context = MigrationContext.configure(
                conn, opts={"include_object": _checked_only, "compare_type": False}
            )
            assert compare_metadata(context, Base.metadata) == []
    finally:
        engine.dispose()
