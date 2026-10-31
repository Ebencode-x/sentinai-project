"""Database access for incidents and suggestions.

Every function takes an open session and an account id, so the same code keeps
working when a deployment moves from one account to many.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.db.models import Account, AccountSettings, Incident, NotificationChannel, Suggestion
from src.models.events import LogIncident, RemediationSuggestion


def default_account_id(db: Session) -> str | None:
    """The account of a single-team deployment: the oldest one."""
    stmt = select(Account.id).order_by(Account.created_at).limit(1)
    return db.execute(stmt).scalar_one_or_none()


def _count_repeat(db: Session, account_id: str, fingerprint: str, seen_at: datetime) -> None:
    db.execute(
        update(Incident)
        .where(Incident.account_id == account_id, Incident.fingerprint == fingerprint)
        .values(occurrence_count=Incident.occurrence_count + 1, last_seen_at=seen_at)
    )
    db.commit()


def insert_incident_if_new(db: Session, account_id: str, incident: LogIncident) -> str | None:
    """Store the incident and return its row id, or None when it was already known.

    A known fingerprint only raises occurrence_count and last_seen_at. When two
    scans race, the unique constraint decides: the loser counts a repeat.
    """
    fingerprint = incident.incident_id
    known = db.execute(
        select(Incident.id).where(
            Incident.account_id == account_id, Incident.fingerprint == fingerprint
        )
    ).scalar_one_or_none()
    if known is None:
        row_id = str(uuid.uuid4())
        db.add(
            Incident(
                id=row_id,
                account_id=account_id,
                fingerprint=fingerprint,
                detected_at=incident.detected_at_utc,
                last_seen_at=incident.detected_at_utc,
                occurrence_count=1,
                severity=incident.severity,
                trigger_line=incident.trigger_line,
                stacktrace=incident.stacktrace,
                context_before_error=incident.context_before_error,
            )
        )
        try:
            db.commit()
            return row_id
        except IntegrityError:
            db.rollback()  # another scan stored it first
    _count_repeat(db, account_id, fingerprint, incident.detected_at_utc)
    return None


def _to_incident(row: Incident) -> LogIncident:
    return LogIncident(
        incident_id=row.fingerprint,
        detected_at_utc=row.detected_at,
        severity=row.severity,
        trigger_line=row.trigger_line,
        stacktrace=row.stacktrace,
        context_before_error=row.context_before_error,
    )


def list_incidents(db: Session, account_id: str, limit: int) -> list[LogIncident]:
    """The latest incidents, oldest first."""
    stmt = (
        select(Incident)
        .where(Incident.account_id == account_id)
        .order_by(Incident.detected_at.desc(), Incident.id.desc())
        .limit(limit)
    )
    return [_to_incident(row) for row in reversed(db.execute(stmt).scalars().all())]


def add_suggestion(
    db: Session, account_id: str, incident_pk: str, s: RemediationSuggestion
) -> None:
    db.add(
        Suggestion(
            id=s.id,
            account_id=account_id,
            incident_pk=incident_pk,
            created_at=s.created_at_utc,
            summary=s.summary,
            proposed_code_fix=s.proposed_code_fix,
            proposed_config_change=s.proposed_config_change,
            confidence=s.confidence,
            risks=s.risks,
            source=s.source,
            provider_error=s.provider_error,
            model=s.model,
            proposed_patch=s.proposed_patch,
            test_guidance=s.test_guidance,
            pr_url=s.pr_url,
            pr_number=s.pr_number,
            patch_file=s.patch_file,
            before_sha=s.before_sha,
            branch_name=s.branch_name,
            autonomy_mode=s.autonomy_mode,
            awaiting_approval=s.awaiting_approval,
        )
    )
    db.commit()


def _to_suggestion(row: Suggestion) -> RemediationSuggestion:
    return RemediationSuggestion(
        id=row.id,
        created_at_utc=row.created_at,
        summary=row.summary,
        proposed_code_fix=row.proposed_code_fix,
        proposed_config_change=row.proposed_config_change,
        confidence=row.confidence,
        risks=row.risks,
        source=row.source,
        provider_error=row.provider_error,
        model=row.model,
        proposed_patch=row.proposed_patch,
        test_guidance=row.test_guidance,
        pr_url=row.pr_url,
        pr_number=row.pr_number,
        patch_file=row.patch_file,
        before_sha=row.before_sha,
        branch_name=row.branch_name,
        autonomy_mode=row.autonomy_mode,
        awaiting_approval=row.awaiting_approval,
    )


def list_suggestions(db: Session, account_id: str, limit: int) -> list[RemediationSuggestion]:
    """The latest suggestions, oldest first."""
    stmt = (
        select(Suggestion)
        .where(Suggestion.account_id == account_id)
        .order_by(Suggestion.created_at.desc(), Suggestion.id.desc())
        .limit(limit)
    )
    return [_to_suggestion(row) for row in reversed(db.execute(stmt).scalars().all())]


def latest_suggestion(db: Session, account_id: str) -> RemediationSuggestion | None:
    stmt = (
        select(Suggestion)
        .where(Suggestion.account_id == account_id)
        .order_by(Suggestion.created_at.desc(), Suggestion.id.desc())
        .limit(1)
    )
    row = db.execute(stmt).scalar_one_or_none()
    return _to_suggestion(row) if row else None


def counts(db: Session, account_id: str) -> dict:
    incidents = db.execute(
        select(func.count()).select_from(Incident).where(Incident.account_id == account_id)
    ).scalar_one()
    rows = db.execute(
        select(Suggestion.source, func.count())
        .where(Suggestion.account_id == account_id)
        .group_by(Suggestion.source)
    ).all()
    by_source = {source: total for source, total in rows}
    return {
        "incidents": incidents,
        "suggestions": sum(by_source.values()),
        "by_source": by_source,
    }


def get_autonomy_mode(db: Session, account_id: str) -> str | None:
    stmt = select(AccountSettings.autonomy_mode).where(AccountSettings.account_id == account_id)
    return db.execute(stmt).scalar_one_or_none()


def set_autonomy_mode(
    db: Session, account_id: str, mode: str, updated_by: str | None = None
) -> None:
    row = db.get(AccountSettings, account_id)
    if row is None:
        db.add(AccountSettings(account_id=account_id, autonomy_mode=mode, updated_by=updated_by))
    else:
        row.autonomy_mode = mode
        row.updated_by = updated_by
    db.commit()


def list_channels(db: Session, account_id: str) -> list[NotificationChannel]:
    stmt = (
        select(NotificationChannel)
        .where(NotificationChannel.account_id == account_id)
        .order_by(NotificationChannel.created_at, NotificationChannel.id)
    )
    return list(db.execute(stmt).scalars().all())


def get_channel(db: Session, account_id: str, channel_id: str) -> NotificationChannel | None:
    stmt = select(NotificationChannel).where(
        NotificationChannel.account_id == account_id, NotificationChannel.id == channel_id
    )
    return db.execute(stmt).scalar_one_or_none()


def add_channel(
    db: Session,
    account_id: str,
    *,
    name: str,
    type_: str,
    url_encrypted: str,
    severities: list[str],
    enabled: bool = True,
) -> NotificationChannel:
    row = NotificationChannel(
        account_id=account_id,
        name=name,
        type=type_,
        url_encrypted=url_encrypted,
        severities=severities,
        enabled=enabled,
    )
    db.add(row)
    db.commit()
    return row


def delete_channel(db: Session, account_id: str, channel_id: str) -> bool:
    result = db.execute(
        delete(NotificationChannel).where(
            NotificationChannel.account_id == account_id, NotificationChannel.id == channel_id
        )
    )
    db.commit()
    return result.rowcount > 0
