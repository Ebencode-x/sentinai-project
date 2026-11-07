"""Per-day activity counts come from the database, bucketed by UTC day."""

from datetime import UTC, datetime, timedelta, timezone

from src.db import activity, sources
from src.db.models import Incident, IngestedEvent, Source

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)


def _at(day: int, hour: int = 12) -> datetime:
    return datetime(2026, 11, day, hour, tzinfo=UTC)


def _source(factory, account_id, name="agrolink") -> str:
    with factory() as db:
        row, _key = sources.create_source(db, account_id, name)
        return row.id


def _event(db, account_id, source_id, number, when):
    db.add(
        IngestedEvent(
            account_id=account_id,
            source_id=source_id,
            event_id=f"evt-{number}",
            occurred_at=when,
            received_at=when,
            message="boom",
            fingerprint=f"fp-{number}",
        )
    )


def _incident(db, account_id, fingerprint, detected, resolved=None):
    db.add(
        Incident(
            account_id=account_id,
            fingerprint=fingerprint,
            detected_at=detected,
            last_seen_at=detected,
            trigger_line="KeyError: 'customer_id'",
            status="resolved" if resolved else "open",
            resolved_at=resolved,
        )
    )


def test_events_are_counted_per_utc_day_and_quiet_days_are_zero(app_db):
    factory, account_id = app_db
    source_id = _source(factory, account_id)
    with factory() as db:
        _event(db, account_id, source_id, 1, _at(7, 0))
        _event(db, account_id, source_id, 2, _at(7, 9))
        _event(db, account_id, source_id, 3, datetime(2026, 11, 6, 23, 59, tzinfo=UTC))
        # 01:30 at UTC+3 on Nov 7 is 22:30 UTC on Nov 6.
        _event(
            db,
            account_id,
            source_id,
            4,
            datetime(2026, 11, 7, 1, 30, tzinfo=timezone(timedelta(hours=3))),
        )
        db.commit()
    with factory() as db:
        result = activity.daily_activity(db, account_id, days=7, now=NOW)
    by_day = {d["date"]: d["events"] for d in result["daily"]}
    assert len(result["daily"]) == 7
    assert result["daily"][0]["date"] == "2026-11-01"
    assert result["daily"][-1]["date"] == "2026-11-07"
    assert by_day["2026-11-07"] == 2
    assert by_day["2026-11-06"] == 2
    assert by_day["2026-11-05"] == 0


def test_new_and_resolved_incidents_are_counted_on_their_own_days(app_db):
    factory, account_id = app_db
    with factory() as db:
        _incident(db, account_id, "fp-a", _at(5), resolved=_at(6))
        _incident(db, account_id, "fp-b", _at(5))
        _incident(db, account_id, "fp-c", _at(7))
        db.commit()
    with factory() as db:
        result = activity.daily_activity(db, account_id, days=7, now=NOW)
    opened = {d["date"]: d["new_incidents"] for d in result["daily"]}
    resolved = {d["date"]: d["resolved"] for d in result["daily"]}
    assert opened["2026-11-05"] == 2
    assert opened["2026-11-06"] == 0
    assert opened["2026-11-07"] == 1
    assert resolved["2026-11-06"] == 1
    assert resolved["2026-11-05"] == 0
    assert result["totals"]["new_incidents"] == 3
    assert result["totals"]["resolved"] == 1


def test_events_older_than_the_window_are_left_out(app_db):
    factory, account_id = app_db
    source_id = _source(factory, account_id)
    with factory() as db:
        _event(db, account_id, source_id, 1, NOW)
        _event(db, account_id, source_id, 2, NOW - timedelta(days=400))
        db.commit()
    with factory() as db:
        result = activity.daily_activity(db, account_id, days=30, now=NOW)
    assert result["totals"]["events"] == 1


def test_streaks_count_consecutive_active_days(app_db):
    factory, account_id = app_db
    source_id = _source(factory, account_id)
    with factory() as db:
        for number, day in enumerate([1, 5, 6, 7]):
            _event(db, account_id, source_id, number, _at(day))
        db.commit()
    with factory() as db:
        totals = activity.daily_activity(db, account_id, days=7, now=NOW)["totals"]
    assert totals["active_days"] == 4
    assert totals["longest_streak"] == 3
    assert totals["current_streak"] == 3


def test_a_quiet_today_does_not_break_the_current_streak(app_db):
    factory, account_id = app_db
    source_id = _source(factory, account_id)
    with factory() as db:
        _event(db, account_id, source_id, 1, _at(5))
        _event(db, account_id, source_id, 2, _at(6))
        db.commit()
    with factory() as db:
        totals = activity.daily_activity(db, account_id, days=7, now=NOW)["totals"]
    assert totals["current_streak"] == 2
    assert totals["longest_streak"] == 2


def test_each_source_gets_its_own_daily_counts_and_status(app_db):
    factory, account_id = app_db
    first = _source(factory, account_id, "agrolink")
    second = _source(factory, account_id, "old-app")
    with factory() as db:
        _event(db, account_id, first, 1, _at(7, 9))
        _event(db, account_id, first, 2, _at(7, 10))
        _event(db, account_id, first, 3, _at(6))
        db.get(Source, first).last_event_at = _at(7, 10)
        db.commit()
    with factory() as db:
        assert sources.revoke_source(db, account_id, second) is True
        result = activity.daily_activity(db, account_id, days=7, now=NOW)
    by_name = {s["name"]: s for s in result["sources"]}
    assert list(by_name) == ["agrolink", "old-app"]
    assert by_name["agrolink"]["daily"] == [0, 0, 0, 0, 0, 1, 2]
    assert by_name["agrolink"]["status"] == "active"
    assert by_name["agrolink"]["last_event_at"] == _at(7, 10)
    assert by_name["old-app"]["status"] == "revoked"
    assert by_name["old-app"]["daily"] == [0] * 7


def test_the_number_of_days_is_kept_in_range(app_db):
    factory, account_id = app_db
    with factory() as db:
        assert len(activity.daily_activity(db, account_id, days=1000, now=NOW)["daily"]) == 366
        assert len(activity.daily_activity(db, account_id, days=0, now=NOW)["daily"]) == 1
