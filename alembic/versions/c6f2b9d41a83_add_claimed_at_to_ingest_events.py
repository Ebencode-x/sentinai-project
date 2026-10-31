"""add claimed_at to ingest_events

Revision ID: c6f2b9d41a83
Revises: b4c91d7e6a15
Create Date: 2026-10-31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c6f2b9d41a83"
down_revision: str | None = "b4c91d7e6a15"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ingest_events",
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ingest_events", "claimed_at")
