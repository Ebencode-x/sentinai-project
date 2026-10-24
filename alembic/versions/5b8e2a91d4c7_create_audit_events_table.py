"""create audit_events table

Revision ID: 5b8e2a91d4c7
Revises: c3e6f7e78fc3
Create Date: 2026-10-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "5b8e2a91d4c7"
down_revision: str | None = "c3e6f7e78fc3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("incident_id", sa.String(length=255), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("provider", sa.String(length=100), nullable=True),
        sa.Column("patch_file", sa.String(length=1024), nullable=True),
        sa.Column("patch_hash", sa.String(length=100), nullable=True),
        sa.Column("policy_decision", sa.String(length=50), nullable=True),
        sa.Column("risk_tier", sa.String(length=50), nullable=True),
        sa.Column("review_required", sa.Boolean(), nullable=False),
        sa.Column("patch_applied", sa.Boolean(), nullable=False),
        sa.Column("tests_passed", sa.Boolean(), nullable=True),
        sa.Column("pr_url", sa.Text(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=True),
    )
    op.create_index("ix_audit_events_timestamp", "audit_events", ["timestamp"])
    op.create_index("ix_audit_events_incident_id", "audit_events", ["incident_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_incident_id", table_name="audit_events")
    op.drop_index("ix_audit_events_timestamp", table_name="audit_events")
    op.drop_table("audit_events")
