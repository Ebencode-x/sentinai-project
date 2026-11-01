"""Event ingest v1: POST /api/v1/events.

A source authenticates with its own API key (Authorization: Bearer snl_...). The
source is taken from the key, never from the request body. The reply is sent only
after the events are stored in the database, so an accepted event is not lost to a
redeploy, and a retry with the same event_id is not counted twice.
"""

from __future__ import annotations

import logging
import os
import threading
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.core.fingerprint import fingerprint
from src.core.rate_limiter import TokenBucket
from src.core.scrub import scrub
from src.db import ingest as event_store
from src.db import sources
from src.db.session import get_db

logger = logging.getLogger("sentinai.events")

router = APIRouter(prefix="/v1/events", tags=["events"])

MAX_BODY_BYTES = 256 * 1024
MAX_EVENTS = 100
MAX_FUTURE = timedelta(minutes=5)
_RATE_PER_MINUTE = int(os.getenv("SENTINAI_EVENTS_RATE_LIMIT", "120"))

_limiters: dict[str, TokenBucket] = {}
_limiters_lock = threading.Lock()

DbDep = Annotated[Session, Depends(get_db)]


class EventIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    event_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.:-]{1,64}$")
    timestamp: datetime | None = None
    level: Literal["warning", "error", "critical"] = "error"
    exception_type: str | None = Field(default=None, max_length=255)
    stacktrace: str | None = Field(default=None, max_length=6000)
    environment: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9_.-]{0,31}$")
    release: str | None = Field(default=None, max_length=64)
    request_id: str | None = Field(default=None, max_length=128)


class EventBatch(BaseModel):
    events: list[EventIn] = Field(min_length=1, max_length=MAX_EVENTS)


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    token = token.strip()
    return token if scheme.lower() == "bearer" and token else None


def _limiter_for(source_id: str) -> TokenBucket:
    with _limiters_lock:
        limiter = _limiters.get(source_id)
        if limiter is None:
            limiter = TokenBucket(capacity=_RATE_PER_MINUTE, refill_per_minute=_RATE_PER_MINUTE)
            _limiters[source_id] = limiter
        return limiter


async def _read_body(request: Request) -> bytes:
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Payload too large")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="Payload too large")
    return bytes(body)


def _unavailable() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail="Events could not be stored. Retry shortly.",
        headers={"Retry-After": "5"},
    )


def _prepare(source_name: str, event: EventIn, now: datetime) -> event_store.NewEvent:
    message = " ".join(scrub(event.message).split()) or "(empty message)"
    stacktrace = scrub(event.stacktrace) if event.stacktrace else None
    exception_type = scrub(event.exception_type) if event.exception_type else None
    occurred = event.timestamp or now
    if occurred.tzinfo is None:
        occurred = occurred.replace(tzinfo=UTC)
    if occurred > now + MAX_FUTURE:
        occurred = now
    return event_store.NewEvent(
        event_id=event.event_id or str(uuid.uuid4()),
        occurred_at=occurred,
        level=event.level,
        message=message,
        exception_type=exception_type,
        stacktrace=stacktrace,
        environment=event.environment,
        release=event.release,
        request_id=event.request_id,
        fingerprint=fingerprint(source_name, message, exception_type, stacktrace),
    )


def _handle(db: Session, key: str | None, raw: bytes) -> dict[str, int]:
    try:
        source = sources.authenticate(db, key)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Could not check an API key")
        raise _unavailable() from exc
    if source is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not _limiter_for(source.id).consume():
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded.",
            headers={"Retry-After": "60"},
        )
    try:
        batch = EventBatch.model_validate_json(raw)
    except ValidationError as exc:
        detail = [
            {"loc": [str(part) for part in err["loc"]], "msg": err["msg"]} for err in exc.errors()
        ]
        raise HTTPException(status_code=422, detail=detail) from exc

    now = datetime.now(UTC)
    prepared = [_prepare(source.name, event, now) for event in batch.events]
    try:
        stored, duplicates = event_store.store_events(db, source, prepared)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Events could not be stored for source %s", source.name)
        raise _unavailable() from exc
    return {"accepted": stored, "duplicates": duplicates}


@router.post("", status_code=202)
async def receive_events(
    request: Request,
    db: DbDep,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, int]:
    key = _bearer(authorization)
    raw = await _read_body(request)
    return await run_in_threadpool(_handle, db, key, raw)
