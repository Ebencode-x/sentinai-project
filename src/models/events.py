"""Domain models representing detected incidents and AI suggestions."""

from __future__ import annotations

from datetime import datetime
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