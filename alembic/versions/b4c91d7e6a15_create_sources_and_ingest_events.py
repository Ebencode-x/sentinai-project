"""create sources and ingest_events tables

Revision ID: b4c91d7e6a15
Revises: a7d3f1c8e902
Create Date: 2026-10-31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b4c91d7e6a15"
down_revision: str | None = "a7d3f1c8e902"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", _TZ, nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("revoked_at", _TZ, nullable=True),
        sa.Column("last_used_at", _TZ, nullable=True),
        sa.Column("last_event_at", _TZ, nullable=True),
        sa.UniqueConstraint("account_id", "name", name="uq_sources_account_name"),
    )
    op.create_index("ix_sources_account_id", "sources", ["account_id"])
    op.create_index("ix_sources_key_prefix", "sources", ["key_prefix"], unique=True)

    op.create_table(
        "ingest_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column(
            "source_id",
            sa.String(length=36),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", _TZ, nullable=False),
        sa.Column("received_at", _TZ, nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("exception_type", sa.String(length=255), nullable=True),
        sa.Column("stacktrace", sa.Text(), nullable=True),
        sa.Column("environment", sa.String(length=32), nullable=True),
        sa.Column("release", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("fingerprint", sa.String(length=255), nullable=False),
        sa.Column(
            "incident_pk",
            sa.String(length=36),
            sa.ForeignKey("incidents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("processed_at", _TZ, nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.UniqueConstraint("source_id", "event_id", name="uq_ingest_events_source_event"),
    )
    op.create_index("ix_ingest_events_account_id", "ingest_events", ["account_id"])
    op.create_index("ix_ingest_events_source_id", "ingest_events", ["source_id"])
    op.create_index("ix_ingest_events_received_at", "ingest_events", ["received_at"])
    op.create_index("ix_ingest_events_fingerprint", "ingest_events", ["fingerprint"])
    op.create_index("ix_ingest_events_incident_pk", "ingest_events", ["incident_pk"])
    op.create_index("ix_ingest_events_processed_at", "ingest_events", ["processed_at"])

    op.add_column("incidents", sa.Column("source", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("incidents", "source")
    op.drop_table("ingest_events")
    op.drop_table("sources")
