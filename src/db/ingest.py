"""Storage of events received from sources."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.db.models import IngestedEvent, Source

MAX_ATTEMPTS = 5


@dataclass(frozen=True)
class NewEvent:
    event_id: str
    occurred_at: datetime
    level: str
    message: str
    exception_type: str | None
    stacktrace: str | None
    environment: str | None
    release: str | None
    request_id: str | None
    fingerprint: str


def store_events(db: Session, source: Source, events: list[NewEvent]) -> tuple[int, int]:
    """Save a batch and return (stored, duplicates).

    An event_id the source already sent is not saved again, so a retry is never
    counted twice. Each event gets its own savepoint, so one duplicate does not
    undo the rest of the batch.
    """
    stored = 0
    duplicates = 0
    for event in events:
        row = IngestedEvent(
            account_id=source.account_id,
            source_id=source.id,
            event_id=event.event_id,
            occurred_at=event.occurred_at,
            level=event.level,
            message=event.message,
            exception_type=event.exception_type,
            stacktrace=event.stacktrace,
            environment=event.environment,
            release=event.release,
            request_id=event.request_id,
            fingerprint=event.fingerprint,
        )
        try:
            with db.begin_nested():
                db.add(row)
        except IntegrityError:
            duplicates += 1
            continue
        stored += 1
    if stored:
        db.execute(
            update(Source)
            .where(Source.id == source.id)
            .values(last_event_at=datetime.now(UTC))
            .execution_options(synchronize_session=False)
        )
    db.commit()
    return stored, duplicates


def queue_counts(db: Session, account_id: str, max_attempts: int = MAX_ATTEMPTS) -> dict[str, int]:
    """How many stored events wait to become incidents, and how many gave up."""
    waiting = (
        select(func.count())
        .select_from(IngestedEvent)
        .where(IngestedEvent.account_id == account_id, IngestedEvent.processed_at.is_(None))
    )
    pending = db.execute(waiting.where(IngestedEvent.attempts < max_attempts)).scalar_one()
    failed = db.execute(waiting.where(IngestedEvent.attempts >= max_attempts)).scalar_one()
    return {"pending": pending, "failed": failed}
