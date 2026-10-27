"""SQLAlchemy models for accounts, users, and sessions.

Design notes (see docs/account-model-design.md):
- One Account per deployment for now (single-team) — table exists so a
  future multi-account cutover is a migration, not a rebuild.
- Role is a flat enum: admin | viewer. No fine-grained permissions.
- Session tokens are opaque, stored server-side, and revocable immediately
  (deleting the row logs the user out) — chosen over JWT for that reason.
- Incidents/suggestions/settings are NOT modeled here — they stay in
  AppState's existing deque + JSON-file-cache mechanism (see
  src/core/state.py). This module only owns auth.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Role(StrEnum):
    ADMIN = "admin"
    VIEWER = "viewer"


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    users: Mapped[list[User]] = relationship(back_populates="account")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(String(20), default=Role.VIEWER)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    account: Mapped[Account] = relationship(back_populates="users")
    sessions: Mapped[list[Session]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Session(Base):
    __tablename__ = "sessions"

    token: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: uuid.uuid4().hex + uuid.uuid4().hex
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="sessions")

    @property
    def is_expired(self) -> bool:
        expires = self.expires_at
        if expires.tzinfo is None:
            # SQLite does not store time zones and returns naive values; they are UTC.
            expires = expires.replace(tzinfo=UTC)
        return datetime.now(UTC) >= expires


class AuditEvent(Base):
    """One row per AI pipeline action. Append-only by convention."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    incident_id: Mapped[str] = mapped_column(String(255), index=True)
    model: Mapped[str | None] = mapped_column(String(255), default=None)
    provider: Mapped[str | None] = mapped_column(String(100), default=None)
    patch_file: Mapped[str | None] = mapped_column(String(1024), default=None)
    patch_hash: Mapped[str | None] = mapped_column(String(100), default=None)
    policy_decision: Mapped[str | None] = mapped_column(String(50), default=None)
    risk_tier: Mapped[str | None] = mapped_column(String(50), default=None)
    review_required: Mapped[bool] = mapped_column(Boolean, default=False)
    patch_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    tests_passed: Mapped[bool | None] = mapped_column(Boolean, default=None)
    pr_url: Mapped[str | None] = mapped_column(Text, default=None)
    failure_reason: Mapped[str | None] = mapped_column(Text, default=None)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str | None] = mapped_column(String(100), default=None)
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, index=True
    )
    archived_by: Mapped[str | None] = mapped_column(String(255), default=None)
