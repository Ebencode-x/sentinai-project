"""add status columns to incidents

Revision ID: d5a8e3f19b27
Revises: c6f2b9d41a83
Create Date: 2026-11-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d5a8e3f19b27"
down_revision: str | None = "c6f2b9d41a83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "incidents",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
    )
    op.add_column("incidents", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("incidents", sa.Column("resolved_by", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("incidents", "resolved_by")
    op.drop_column("incidents", "resolved_at")
    op.drop_column("incidents", "status")
