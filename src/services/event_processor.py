"""Turns stored events into incidents.

Events arrive through POST /api/v1/events and are stored first. This worker claims
them in small batches, groups them into incidents by fingerprint, and sends each new
incident through the same analysis as before: suggestion, audit, rollback record and
notifications.

A claim is a lease (claimed_at). The batch is selected with FOR UPDATE SKIP LOCKED,
so two workers never take the same event, and the lock is held only while claiming,
not while the model runs. A worker that dies leaves its events unprocessed, and they
become claimable again once the lease runs out. An event is tried a few times, then
left for a person to look at (see events_failed in /stats).

The incident and the "processed" mark are saved in one transaction, so an event is
never counted twice. A failure in the analysis that follows is recorded, not retried:
the incident is already stored.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import or_, select, update

from src.db import repository
from src.db.ingest import MAX_ATTEMPTS
from src.db.models import IngestedEvent, Source
from src.models.events import LogIncident

if TYPE_CHECKING:
    from src.core.state import AppState

logger = logging.getLogger("sentinai.events")

LEASE = timedelta(minutes=10)
BATCH_SIZE = 5
_OFF_VALUES = {"0", "false", "no", "off"}
_SEVERITY = {"warning": "warning", "error": "critical", "critical": "critical"}


def worker_enabled() -> bool:
    return os.getenv("SENTINAI_EVENT_WORKER", "1").strip().lower() not in _OFF_VALUES


def poll_seconds() -> float:
    try:
        return max(0.1, float(os.getenv("SENTINAI_EVENT_POLL_SECONDS", "2")))
    except ValueError:
        return 2.0


@dataclass(frozen=True)
class ClaimedEvent:
    id: str
    account_id: str
    source: str
    fingerprint: str
    occurred_at: datetime
    level: str
    message: str
    exception_type: str | None
    stacktrace: str | None
    environment: str | None
    release: str | None
    request_id: str | None
    attempts: int


def _trigger_line(event: ClaimedEvent) -> str:
    kind = event.exception_type
    if kind and not event.message.startswith(kind):
        return f"{kind}: {event.message}"
    return event.message


def _context(event: ClaimedEvent) -> str:
    pairs = (
        ("source", event.source),
        ("environment", event.environment),
        ("release", event.release),
        ("request_id", event.request_id),
    )
    return " ".join(f"{key}={value}" for key, value in pairs if value)


def to_incident(event: ClaimedEvent) -> LogIncident:
    return LogIncident(
        incident_id=event.fingerprint,
        detected_at_utc=event.occurred_at,
        severity=_SEVERITY.get(event.level, "critical"),
        trigger_line=_trigger_line(event),
        stacktrace=event.stacktrace or "",
        context_before_error=_context(event),
        source=event.source,
    )


class EventProcessor:
    def __init__(
        self,
        state: AppState,
        *,
        batch_size: int = BATCH_SIZE,
        lease: timedelta = LEASE,
        max_attempts: int = MAX_ATTEMPTS,
    ) -> None:
        self.state = state
        self.batch_size = batch_size
        self.lease = lease
        self.max_attempts = max_attempts

    def claim(self) -> list[ClaimedEvent]:
        """Take the oldest waiting events for this worker. Locks are held only briefly."""
        now = datetime.now(UTC)
        stmt = (
            select(IngestedEvent, Source.name)
            .join(Source, Source.id == IngestedEvent.source_id)
            .where(
                IngestedEvent.processed_at.is_(None),
                IngestedEvent.attempts < self.max_attempts,
                or_(
                    IngestedEvent.claimed_at.is_(None),
                    IngestedEvent.claimed_at < now - self.lease,
                ),
            )
            .order_by(IngestedEvent.received_at, IngestedEvent.id)
            .limit(self.batch_size)
            .with_for_update(skip_locked=True, of=IngestedEvent)
        )
        claimed: list[ClaimedEvent] = []
        with self.state.session_factory() as db:
            for event, source_name in db.execute(stmt).all():
                event.claimed_at = now
                event.attempts += 1
                claimed.append(
                    ClaimedEvent(
                        id=event.id,
                        account_id=event.account_id,
                        source=source_name,
                        fingerprint=event.fingerprint,
                        occurred_at=event.occurred_at,
                        level=event.level,
                        message=event.message,
                        exception_type=event.exception_type,
                        stacktrace=event.stacktrace,
                        environment=event.environment,
                        release=event.release,
                        request_id=event.request_id,
                        attempts=event.attempts,
                    )
                )
            db.commit()
        return claimed

    def run_once(self) -> int:
        """Claim and handle one batch. Returns how many events were claimed."""
        claimed = self.claim()
        for event in claimed:
            try:
                self._process(event)
            except Exception as exc:
                logger.exception("[events] Event %s from %s failed", event.id, event.source)
                self._record_failure(event.id, exc)
        return len(claimed)

    def _process(self, event: ClaimedEvent) -> None:
        incident = to_incident(event)
        with self.state.session_factory() as db:
            incident_pk, is_new = repository.upsert_incident(
                db, event.account_id, incident, commit=False
            )
            db.execute(
                update(IngestedEvent)
                .where(IngestedEvent.id == event.id)
                .values(incident_pk=incident_pk, processed_at=datetime.now(UTC), last_error=None)
            )
            db.commit()
        if not is_new:
            return
        try:
            self.state.analyse_new_incident(incident, event.account_id, incident_pk)
        except Exception as exc:
            logger.exception("[events] Analysis failed for incident %s", incident.incident_id)
            self._record_failure(event.id, exc, prefix="analysis failed: ")

    def _record_failure(self, event_id: str, exc: Exception, prefix: str = "") -> None:
        lines = str(exc).splitlines()
        detail = lines[0][:300] if lines else ""
        text = f"{prefix}{type(exc).__name__}: {detail}"
        try:
            with self.state.session_factory() as db:
                db.execute(
                    update(IngestedEvent)
                    .where(IngestedEvent.id == event_id)
                    .values(last_error=text)
                )
                db.commit()
        except Exception:
            logger.warning("[events] Could not record the failure of %s", event_id, exc_info=True)


async def run_forever(
    processor: EventProcessor,
    stop: asyncio.Event,
    interval: float,
    failure_delay: float = 10.0,
) -> None:
    """Handle events until stop is set. A failing pass is logged and tried again."""
    logger.info("[events] Worker started")
    while not stop.is_set():
        delay = interval
        try:
            claimed = await asyncio.to_thread(processor.run_once)
        except Exception:
            logger.exception("[events] A worker pass failed; trying again shortly")
            claimed, delay = 0, max(interval, failure_delay)
        if claimed >= processor.batch_size:
            continue
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=delay)
    logger.info("[events] Worker stopped")
