"""Event sources and their API keys."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.api_keys import generate_key, matches, prefix_of
from src.db.models import Source

NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
TOUCH_INTERVAL = timedelta(minutes=1)
_DUMMY_HASH = "0" * 64


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def create_source(
    db: Session, account_id: str, name: str, created_by: str | None = None
) -> tuple[Source, str]:
    """Create a source and return it with its key. The key cannot be shown again."""
    if not NAME_PATTERN.match(name):
        raise ValueError("A source name uses lowercase letters, digits, - and _ (up to 32).")
    key, prefix, key_hash = generate_key()
    row = Source(
        account_id=account_id,
        name=name,
        key_prefix=prefix,
        key_hash=key_hash,
        created_by=created_by,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError(f"A source named '{name}' already exists.") from exc
    return row, key


def list_sources(db: Session, account_id: str) -> list[Source]:
    stmt = (
        select(Source)
        .where(Source.account_id == account_id)
        .order_by(Source.created_at, Source.name)
    )
    return list(db.execute(stmt).scalars().all())


def get_source(db: Session, account_id: str, source_id: str) -> Source | None:
    stmt = select(Source).where(Source.account_id == account_id, Source.id == source_id)
    return db.execute(stmt).scalar_one_or_none()


def revoke_source(db: Session, account_id: str, source_id: str) -> bool:
    """Stop accepting the source's key. Safe to repeat."""
    row = get_source(db, account_id, source_id)
    if row is None:
        return False
    if row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        db.commit()
    return True


def rotate_key(db: Session, account_id: str, source_id: str) -> str | None:
    """Issue a new key. The old one stops working at once."""
    row = get_source(db, account_id, source_id)
    if row is None:
        return None
    if row.revoked_at is not None:
        raise ValueError("This source is revoked.")
    key, prefix, key_hash = generate_key()
    row.key_prefix = prefix
    row.key_hash = key_hash
    db.commit()
    return key


def authenticate(db: Session, key: str | None) -> Source | None:
    """The active source a key belongs to, or None for any bad, unknown or revoked key."""
    prefix = prefix_of(key)
    if prefix is None:
        return None
    row = db.execute(select(Source).where(Source.key_prefix == prefix)).scalar_one_or_none()
    if row is None:
        matches(key or "", _DUMMY_HASH)  # keep the time spent similar for unknown keys
        return None
    if not matches(key or "", row.key_hash) or row.revoked_at is not None:
        return None
    now = datetime.now(UTC)
    if row.last_used_at is None or now - _aware(row.last_used_at) > TOUCH_INTERVAL:
        row.last_used_at = now
        db.commit()
    return row
