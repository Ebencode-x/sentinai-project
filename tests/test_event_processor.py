"""The event worker: stored events become incidents once, and failures are retried."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from src.core.fingerprint import fingerprint
from src.core.state import AppState
from src.db import ingest as event_store
from src.db import repository, sources
from src.db.models import Incident, IngestedEvent, Source, Suggestion
from src.models.events import LogIncident, RemediationSuggestion
from src.services.event_processor import (
    ClaimedEvent,
    EventProcessor,
    poll_seconds,
    run_forever,
    to_incident,
    worker_enabled,
)


def _suggestion() -> RemediationSuggestion:
    return RemediationSuggestion(
        summary="Guard the lookup",
        proposed_code_fix="use dict.get",
        proposed_config_change="none",
        confidence=0.8,
        risks="low",
    )


@pytest.fixture
def world(app_db):
    factory, account_id = app_db
    state = AppState(session_factory=factory)
    state._record_audit = lambda incident, suggestion: None
    engine = MagicMock()
    engine.suggest_fix.return_value = _suggestion()
    state.remediation_engine = engine
    return SimpleNamespace(
        factory=factory,
        account_id=account_id,
        state=state,
        engine=engine,
        processor=EventProcessor(state),
    )


def _event(
    message: str = "boom",
    *,
    source: str = "agrolink",
    at: datetime | None = None,
    level: str = "error",
    exception_type: str | None = None,
    stacktrace: str | None = None,
    environment: str | None = None,
    release: str | None = None,
    request_id: str | None = None,
) -> event_store.NewEvent:
    return event_store.NewEvent(
        event_id=str(uuid.uuid4()),
        occurred_at=at or datetime.now(UTC),
        level=level,
        message=message,
        exception_type=exception_type,
        stacktrace=stacktrace,
        environment=environment,
        release=release,
        request_id=request_id,
        fingerprint=fingerprint(source, message, exception_type, stacktrace),
    )


def _store(world, *events, source_name: str = "agrolink"):
    with world.factory() as db:
        source = db.scalars(select(Source).where(Source.name == source_name)).one_or_none()
        if source is None:
            source, _key = sources.create_source(db, world.account_id, source_name)
        return event_store.store_events(db, source, list(events))


def _only_event(world) -> IngestedEvent:
    with world.factory() as db:
        return db.scalars(select(IngestedEvent)).one()


def _claimed(**over) -> ClaimedEvent:
    base = dict(
        id="e1",
        account_id="a1",
        source="agrolink",
        fingerprint="fp",
        occurred_at=datetime.now(UTC),
        level="error",
        message="boom",
        exception_type=None,
        stacktrace=None,
        environment=None,
        release=None,
        request_id=None,
        attempts=1,
    )
    return ClaimedEvent(**{**base, **over})


def _always_fail(*_args, **_kwargs):
    raise RuntimeError("database hiccup")


# ---- turning an event into an incident -----------------------------------------


@pytest.mark.parametrize(
    "level, severity", [("warning", "warning"), ("error", "critical"), ("critical", "critical")]
)
def test_the_event_level_decides_the_incident_severity(level, severity):
    assert to_incident(_claimed(level=level)).severity == severity


def test_the_incident_text_names_the_exception_once():
    named = to_incident(_claimed(message="customer 7 missing", exception_type="KeyError"))
    assert named.trigger_line == "KeyError: customer 7 missing"
    already = to_incident(_claimed(message="KeyError: 'x'", exception_type="KeyError"))
    assert already.trigger_line == "KeyError: 'x'"


def test_the_context_carries_where_the_error_happened():
    incident = to_incident(_claimed(environment="production", release="abc123", request_id="r-1"))
    for part in ("source=agrolink", "environment=production", "release=abc123", "request_id=r-1"):
        assert part in incident.context_before_error
    assert incident.source == "agrolink"


# ---- handling events -------------------------------------------------------------


def test_a_stored_event_becomes_an_incident_with_a_suggestion_and_an_alert(world):
    _store(
        world,
        _event(
            "KeyError: 'customer_id'",
            exception_type="KeyError",
            environment="production",
            release="abc123",
        ),
    )
    with patch("src.core.state.notify") as notify:
        assert world.processor.run_once() == 1
    with world.factory() as db:
        incident = db.scalars(select(Incident)).one()
        suggestion = db.scalars(select(Suggestion)).one()
    event = _only_event(world)
    assert incident.source == "agrolink"
    assert incident.severity == "critical"
    assert "release=abc123" in incident.context_before_error
    assert suggestion.incident_pk == incident.id
    assert event.processed_at is not None
    assert event.incident_pk == incident.id
    assert event.last_error is None
    assert event.attempts == 1
    notify.assert_called_once()


def test_a_repeat_is_counted_on_the_incident_and_not_analysed_again(world):
    _store(world, _event("Order 123 not found"), _event("Order 456 not found"))
    with patch("src.core.state.notify") as notify:
        assert world.processor.run_once() == 2
    with world.factory() as db:
        incident = db.scalars(select(Incident)).one()
    assert incident.occurrence_count == 2
    assert world.engine.suggest_fix.call_count == 1
    notify.assert_called_once()


def test_two_services_with_the_same_message_are_two_incidents(world):
    _store(world, _event("boom", source="agrolink"))
    _store(world, _event("boom", source="orders-api"), source_name="orders-api")
    with patch("src.core.state.notify"):
        world.processor.run_once()
    with world.factory() as db:
        found = {row.source for row in db.scalars(select(Incident)).all()}
    assert found == {"agrolink", "orders-api"}
    assert world.engine.suggest_fix.call_count == 2


def test_the_last_seen_time_never_moves_backwards(world):
    now = datetime.now(UTC)
    _store(world, _event("late", at=now))
    with patch("src.core.state.notify"):
        world.processor.run_once()
        _store(world, _event("late", at=now - timedelta(hours=1)))
        world.processor.run_once()
    with world.factory() as db:
        incident = db.scalars(select(Incident)).one()
    assert incident.occurrence_count == 2
    assert abs(incident.last_seen_at - now) < timedelta(seconds=1)


def test_the_dashboard_model_carries_the_source(world):
    _store(world, _event("boom"))
    with patch("src.core.state.notify"):
        world.processor.run_once()
    with world.factory() as db:
        shown = repository.list_incidents(db, world.account_id, 10)
    assert [incident.source for incident in shown] == ["agrolink"]


def test_events_are_handled_oldest_first_in_batches(world):
    for word in ("alpha", "bravo", "charlie"):
        _store(world, _event(word))
    processor = EventProcessor(world.state, batch_size=2)
    with patch("src.core.state.notify"):
        assert [processor.run_once() for _ in range(3)] == [2, 1, 0]
    with world.factory() as db:
        order = [
            row.trigger_line for row in db.scalars(select(Incident).order_by(Incident.detected_at))
        ]
    assert order == ["alpha", "bravo", "charlie"]


# ---- claims and failures ---------------------------------------------------------


def test_claimed_events_are_not_handed_out_again_until_the_lease_ends(world):
    _store(world, _event("a"))
    first = world.processor.claim()
    assert len(first) == 1
    assert world.processor.claim() == []
    expired = EventProcessor(world.state, lease=timedelta(0)).claim()
    assert [event.id for event in expired] == [first[0].id]


def test_a_failed_event_is_retried_after_its_lease_and_then_succeeds(world, monkeypatch):
    _store(world, _event("boom"))
    real = repository.upsert_incident
    calls = []

    def flaky(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("database hiccup")
        return real(*args, **kwargs)

    monkeypatch.setattr(repository, "upsert_incident", flaky)
    processor = EventProcessor(world.state, lease=timedelta(0))
    with patch("src.core.state.notify"):
        processor.run_once()
        failed = _only_event(world)
        assert failed.processed_at is None
        assert failed.attempts == 1
        assert "database hiccup" in failed.last_error
        processor.run_once()
    done = _only_event(world)
    assert done.processed_at is not None
    assert done.attempts == 2
    assert done.last_error is None


def test_an_event_that_keeps_failing_is_left_for_a_person(world, monkeypatch):
    _store(world, _event("boom"))
    monkeypatch.setattr(repository, "upsert_incident", _always_fail)
    processor = EventProcessor(world.state, lease=timedelta(0), max_attempts=2)
    assert [processor.run_once() for _ in range(3)] == [1, 1, 0]
    with world.factory() as db:
        counts = event_store.queue_counts(db, world.account_id, max_attempts=2)
    assert counts == {"pending": 0, "failed": 1}


def test_a_failed_analysis_is_recorded_but_the_incident_stays_stored(world):
    world.engine.suggest_fix.side_effect = RuntimeError("model exploded")
    _store(world, _event("boom"))
    with patch("src.core.state.notify") as notify:
        assert world.processor.run_once() == 1
        assert world.processor.run_once() == 0
    event = _only_event(world)
    assert event.processed_at is not None
    assert "analysis failed" in event.last_error
    assert "model exploded" in event.last_error
    with world.factory() as db:
        assert db.scalars(select(Incident)).one() is not None
    notify.assert_not_called()


# ---- the work queue ----------------------------------------------------------------


def test_the_queue_counts_waiting_events(world):
    _store(world, _event("a"), _event("b"))
    with world.factory() as db:
        assert event_store.queue_counts(db, world.account_id) == {"pending": 2, "failed": 0}
    assert world.state.stats_snapshot()["events_pending"] == 2
    with patch("src.core.state.notify"):
        world.processor.run_once()
    assert world.state.stats_snapshot()["events_pending"] == 0


def test_upsert_reports_new_then_repeat_and_can_be_rolled_back(app_db):
    factory, account_id = app_db
    incident = LogIncident(
        incident_id="fp-up",
        detected_at_utc=datetime.now(UTC),
        trigger_line="boom",
        stacktrace="",
    )
    with factory() as db:
        first_id, first_new = repository.upsert_incident(db, account_id, incident)
        second_id, second_new = repository.upsert_incident(db, account_id, incident)
    assert (first_new, second_new) == (True, False)
    assert first_id == second_id
    other = incident.model_copy(update={"incident_id": "fp-rolled-back"})
    with factory() as db:
        repository.upsert_incident(db, account_id, other, commit=False)
        db.rollback()
    with factory() as db:
        assert {row.fingerprint for row in db.scalars(select(Incident))} == {"fp-up"}


# ---- the loop and its switches -----------------------------------------------------


def test_the_worker_loop_handles_events_and_stops_when_asked(world):
    _store(world, _event("boom"))

    async def scenario():
        stop = asyncio.Event()
        task = asyncio.create_task(run_forever(world.processor, stop, 0.05))
        try:
            for _ in range(200):
                await asyncio.sleep(0.05)
                if _only_event(world).processed_at is not None:
                    break
        finally:
            stop.set()
            await asyncio.wait_for(task, 10)

    with patch("src.core.state.notify"):
        asyncio.run(scenario())
    with world.factory() as db:
        assert db.scalars(select(Incident)).one() is not None


def test_the_worker_loop_survives_a_failing_pass():
    calls = []

    def flaky() -> int:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("database down")
        return 0

    processor = MagicMock(batch_size=20)
    processor.run_once.side_effect = flaky

    async def scenario():
        stop = asyncio.Event()
        task = asyncio.create_task(run_forever(processor, stop, 0.01, failure_delay=0.01))
        try:
            for _ in range(200):
                await asyncio.sleep(0.02)
                if len(calls) >= 3:
                    break
        finally:
            stop.set()
            await asyncio.wait_for(task, 5)

    asyncio.run(scenario())
    assert len(calls) >= 3


@pytest.mark.parametrize(
    "value, expected",
    [("1", True), ("true", True), ("0", False), ("off", False), ("No", False), (" false ", False)],
)
def test_the_worker_switch(monkeypatch, value, expected):
    monkeypatch.setenv("SENTINAI_EVENT_WORKER", value)
    assert worker_enabled() is expected


def test_the_worker_is_on_by_default(monkeypatch):
    monkeypatch.delenv("SENTINAI_EVENT_WORKER", raising=False)
    assert worker_enabled() is True


def test_the_poll_interval_has_a_default_a_floor_and_ignores_nonsense(monkeypatch):
    monkeypatch.delenv("SENTINAI_EVENT_POLL_SECONDS", raising=False)
    assert poll_seconds() == 2.0
    monkeypatch.setenv("SENTINAI_EVENT_POLL_SECONDS", "0")
    assert poll_seconds() == 0.1
    monkeypatch.setenv("SENTINAI_EVENT_POLL_SECONDS", "soon")
    assert poll_seconds() == 2.0
