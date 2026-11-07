"""Per-day activity for the overview: events received, new and resolved incidents.

Days are UTC days. The counts come straight from the database, so they cover
everything received and not only the latest audit rows. An incident counts as
resolved on the day it was resolved only while it stays resolved, because
reopening it clears the resolve time.
"""

from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import Date, cast, func, literal_column, select
from sqlalchemy.orm import Session

from src.db.models import Incident, IngestedEvent, Source

MAX_DAYS = 366
SOURCE_WINDOW_DAYS = 30


def _utc_day(column):
    return cast(func.timezone(literal_column("'UTC'"), column), Date)


def _start_of(day: date) -> datetime:
    return datetime.combine(day, datetime.min.time(), tzinfo=UTC)


def _streaks(active: list[bool]) -> tuple[int, int]:
    """The longest run of active days, and the run that ends today or yesterday."""
    longest = run = 0
    for flag in active:
        run = run + 1 if flag else 0
        longest = max(longest, run)
    trimmed = active[:-1] if active and not active[-1] else active
    current = 0
    for flag in reversed(trimmed):
        if not flag:
            break
        current += 1
    return longest, current


def daily_activity(
    db: Session, account_id: str, days: int = 182, now: datetime | None = None
) -> dict[str, Any]:
    """One entry per UTC day, oldest first, with zeros for quiet days."""
    days = max(1, min(days, MAX_DAYS))
    today = (now or datetime.now(UTC)).astimezone(UTC).date()
    dates = [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]
    since = _start_of(dates[0])

    received_day = _utc_day(IngestedEvent.received_at)
    events = {
        day: total
        for day, total in db.execute(
            select(received_day, func.count())
            .where(IngestedEvent.account_id == account_id, IngestedEvent.received_at >= since)
            .group_by(received_day)
        ).all()
    }

    opened_day = _utc_day(Incident.detected_at)
    opened = {
        day: total
        for day, total in db.execute(
            select(opened_day, func.count())
            .where(Incident.account_id == account_id, Incident.detected_at >= since)
            .group_by(opened_day)
        ).all()
    }

    resolved_day = _utc_day(Incident.resolved_at)
    resolved = {
        day: total
        for day, total in db.execute(
            select(resolved_day, func.count())
            .where(
                Incident.account_id == account_id,
                Incident.resolved_at.is_not(None),
                Incident.resolved_at >= since,
            )
            .group_by(resolved_day)
        ).all()
    }

    daily = [
        {
            "date": day.isoformat(),
            "events": events.get(day, 0),
            "new_incidents": opened.get(day, 0),
            "resolved": resolved.get(day, 0),
        }
        for day in dates
    ]

    window = dates[-SOURCE_WINDOW_DAYS:]
    per_source = {
        (source_id, day): total
        for source_id, day, total in db.execute(
            select(IngestedEvent.source_id, received_day, func.count())
            .where(
                IngestedEvent.account_id == account_id,
                IngestedEvent.received_at >= _start_of(window[0]),
            )
            .group_by(IngestedEvent.source_id, received_day)
        ).all()
    }
    rows = db.execute(
        select(Source).where(Source.account_id == account_id).order_by(Source.name)
    ).scalars()
    source_list = [
        {
            "id": row.id,
            "name": row.name,
            "status": "revoked" if row.revoked_at else "active",
            "last_event_at": row.last_event_at,
            "daily": [per_source.get((row.id, day), 0) for day in window],
        }
        for row in rows
    ]

    active = [d["events"] > 0 or d["new_incidents"] > 0 for d in daily]
    longest, current = _streaks(active)
    return {
        "days": days,
        "daily": daily,
        "totals": {
            "events": sum(d["events"] for d in daily),
            "new_incidents": sum(d["new_incidents"] for d in daily),
            "resolved": sum(d["resolved"] for d in daily),
            "active_days": sum(active),
            "longest_streak": longest,
            "current_streak": current,
        },
        "sources": source_list,
    }
