"""Domain models representing detected incidents and AI suggestions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class LogIncident(BaseModel):
    """Structured representation of an error incident from application logs."""

    incident_id: str = Field(..., description="Stable fingerprint for deduplication.")
    detected_at_utc: datetime
    severity: Literal["warning", "critical"] = "critical"
    trigger_line: str
    stacktrace: str
    context_before_error: str = ""


class RemediationSuggestion(BaseModel):
    """LLM-generated recommendation for remediation.

    Milestone 2 additions:
    - proposed_patch: concrete code snippet or unified diff the LLM suggests applying.
    - test_guidance: unit-test hints to validate the patch before rollout.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))
    summary: str
    proposed_code_fix: str
    proposed_config_change: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    risks: str
    source: Literal["stub", "provider", "fallback"] = "stub"
    provider_error: str | None = None

    # Milestone 2 fields — optional so existing data stays valid.
    proposed_patch: str | None = Field(
        default=None,
        description="Concrete code patch or unified diff suggested by the LLM.",
    )
    test_guidance: str | None = Field(
        default=None,
        description="Unit-test hints to validate the patch before rollout.",
    )
    pr_url: str | None = Field(
        default=None,
        description="GitHub PR URL opened by SentinAI for this suggestion.",
    )
    pr_number: int | None = Field(
        default=None,
        description="GitHub PR number opened by SentinAI for this suggestion.",
    )
    patch_file: str | None = Field(
        default=None,
        description="File path targeted by the committed patch, derived from the diff.",
    )
    before_sha: str | None = Field(
        default=None,
        description="Blob sha of patch_file immediately before the patch was committed. "
        "Used internally to build rollback ledger entries.",
    )
    branch_name: str | None = Field(
        default=None,
        description="Branch SentinAI committed the patch to. Used internally for rollback.",
    )
    patch_file: str | None = Field(
        default=None,
        description="Repo-relative path of the file patched in the auto-patch PR.",
    )
    autonomy_mode: str | None = Field(
        default=None,
        description="Autonomy mode in effect when this suggestion was generated.",
    )
    awaiting_approval: bool = Field(
        default=False,
        description=(
            "True when a patch was proposed but withheld from auto-PR "
            "because autonomy_mode is propose_only."
        ),
    )
