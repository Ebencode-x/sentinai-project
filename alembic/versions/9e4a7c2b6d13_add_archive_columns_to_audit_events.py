"""add archive columns to audit_events

Revision ID: 9e4a7c2b6d13
Revises: 5b8e2a91d4c7
Create Date: 2026-10-27 15:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9e4a7c2b6d13"
down_revision: str | None = "5b8e2a91d4c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "audit_events",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "audit_events",
        sa.Column("archived_by", sa.String(length=255), nullable=True),
    )
    op.create_index(op.f("ix_audit_events_archived_at"), "audit_events", ["archived_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_events_archived_at"), table_name="audit_events")
    op.drop_column("audit_events", "archived_by")
    op.drop_column("audit_events", "archived_at")
