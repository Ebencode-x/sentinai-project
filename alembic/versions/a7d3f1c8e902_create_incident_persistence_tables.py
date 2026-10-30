"""create incident persistence tables

Revision ID: a7d3f1c8e902
Revises: 9e4a7c2b6d13
Create Date: 2026-10-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a7d3f1c8e902"
down_revision: str | None = "9e4a7c2b6d13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("fingerprint", sa.String(length=255), nullable=False),
        sa.Column("detected_at", _TZ, nullable=False),
        sa.Column("last_seen_at", _TZ, nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("trigger_line", sa.Text(), nullable=False),
        sa.Column("stacktrace", sa.Text(), nullable=False),
        sa.Column("context_before_error", sa.Text(), nullable=False),
        sa.UniqueConstraint("account_id", "fingerprint", name="uq_incidents_account_fingerprint"),
    )
    op.create_index("ix_incidents_account_id", "incidents", ["account_id"])
    op.create_index("ix_incidents_detected_at", "incidents", ["detected_at"])

    op.create_table(
        "suggestions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column(
            "incident_pk",
            sa.String(length=36),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", _TZ, nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("proposed_code_fix", sa.Text(), nullable=False),
        sa.Column("proposed_config_change", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("risks", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("provider_error", sa.Text(), nullable=True),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("proposed_patch", sa.Text(), nullable=True),
        sa.Column("test_guidance", sa.Text(), nullable=True),
        sa.Column("pr_url", sa.Text(), nullable=True),
        sa.Column("pr_number", sa.Integer(), nullable=True),
        sa.Column("patch_file", sa.String(length=1024), nullable=True),
        sa.Column("before_sha", sa.String(length=100), nullable=True),
        sa.Column("branch_name", sa.String(length=255), nullable=True),
        sa.Column("autonomy_mode", sa.String(length=50), nullable=True),
        sa.Column("awaiting_approval", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_suggestions_account_id", "suggestions", ["account_id"])
    op.create_index("ix_suggestions_incident_pk", "suggestions", ["incident_pk"])
    op.create_index("ix_suggestions_created_at", "suggestions", ["created_at"])

    op.create_table(
        "rollback_ledger",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("fingerprint", sa.String(length=255), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("pr_url", sa.Text(), nullable=True),
        sa.Column("branch_name", sa.String(length=255), nullable=True),
        sa.Column("patch_file", sa.String(length=1024), nullable=False),
        sa.Column("before_sha", sa.String(length=100), nullable=False),
        sa.Column("after_sha", sa.String(length=100), nullable=True),
        sa.Column("merge_commit_sha", sa.String(length=100), nullable=True),
        sa.Column("rollback_current_sha", sa.String(length=100), nullable=True),
        sa.Column("revert_commit_sha", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("opened_at", _TZ, nullable=False),
    )
    op.create_index("ix_rollback_ledger_account_id", "rollback_ledger", ["account_id"])
    op.create_index("ix_rollback_ledger_fingerprint", "rollback_ledger", ["fingerprint"])
    op.create_index("ix_rollback_ledger_status", "rollback_ledger", ["status"])
    op.create_index("ix_rollback_ledger_opened_at", "rollback_ledger", ["opened_at"])

    op.create_table(
        "account_settings",
        sa.Column(
            "account_id", sa.String(length=36), sa.ForeignKey("accounts.id"), primary_key=True
        ),
        sa.Column("autonomy_mode", sa.String(length=50), nullable=False),
        sa.Column("updated_at", _TZ, nullable=False),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
    )

    op.create_table(
        "notification_channels",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("url_encrypted", sa.Text(), nullable=False),
        sa.Column(
            "severities", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", _TZ, nullable=False),
    )
    op.create_index("ix_notification_channels_account_id", "notification_channels", ["account_id"])


def downgrade() -> None:
    op.drop_table("notification_channels")
    op.drop_table("account_settings")
    op.drop_table("rollback_ledger")
    op.drop_table("suggestions")
    op.drop_table("incidents")
