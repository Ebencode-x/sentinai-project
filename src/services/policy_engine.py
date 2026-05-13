"""Patch Policy Engine — A1.

Validates every AI-proposed patch against sentinai-policy.yml before
any action is taken. The pipeline must call check() and handle the result
before calling PatchRunner or GitHubClient.

Decision matrix
---------------
ALLOW   → patch meets all constraints, proceed automatically
REVIEW  → patch is medium-risk, human approval required
BLOCK   → patch violates policy, discard immediately
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from src.services.patch_semantic_validator import (
    PatchSemanticValidator,
)

logger = logging.getLogger(__name__)

# Module-level singleton — one validator instance, zero re-init cost.
_semantic_validator = PatchSemanticValidator()

_DEFAULT_POLICY = Path(__file__).resolve().parent.parent.parent / "sentinai-policy.yml"


class Decision(StrEnum):
    ALLOW = "allow"
    REVIEW = "review"
    BLOCK = "block"


@dataclass(frozen=True)
class PolicyResult:
    decision: Decision
    reasons: tuple[str, ...] = field(default_factory=tuple)
    risk_tier: str = "low"

    @property
    def blocked(self) -> bool:
        return self.decision is Decision.BLOCK

    @property
    def requires_review(self) -> bool:
        return self.decision is Decision.REVIEW


@dataclass
class PatchPolicyEngine:
    """Load policy from YAML and validate patch proposals.

    Parameters
    ----------
    policy_path:
        Path to sentinai-policy.yml. Defaults to repo root.
    """

    policy_path: Path = field(default_factory=lambda: _DEFAULT_POLICY)
    _policy: dict[str, Any] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self._load()

    def _load(self) -> None:
        try:
            text = self.policy_path.read_text(encoding="utf-8")
            self._policy = yaml.safe_load(text) or {}
            logger.info("Policy loaded from %s", self.policy_path)
        except FileNotFoundError:
            logger.warning(
                "Policy file not found: %s — using permissive defaults",
                self.policy_path,
            )
            self._policy = {}

    def reload(self) -> None:
        """Hot-reload policy without restarting the process."""
        self._load()

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def check(
        self,
        patch: str,
        patch_file: str,
        files_changed: int = 1,
    ) -> PolicyResult:
        """Validate a proposed patch. Returns PolicyResult with decision."""
        reasons: list[str] = []

        # 1 — blocked paths
        if self._is_blocked_path(patch_file):
            reasons.append(f"blocked path: {patch_file}")
            return PolicyResult(decision=Decision.BLOCK, reasons=tuple(reasons), risk_tier="high")

        # 2 — allowed paths check
        if not self._is_allowed_path(patch_file):
            reasons.append(f"path not in allowed_paths: {patch_file}")
            return PolicyResult(decision=Decision.BLOCK, reasons=tuple(reasons), risk_tier="high")

        # 3 — forbidden patterns in patch content
        forbidden = self._check_forbidden_patterns(patch)
        if forbidden:
            for p in forbidden:
                reasons.append(f"forbidden pattern: {p!r}")
            return PolicyResult(decision=Decision.BLOCK, reasons=tuple(reasons), risk_tier="high")

        # 4 — max files changed
        max_files = self._policy.get("max_files_changed", 5)
        if files_changed > max_files:
            reasons.append(f"too many files changed: {files_changed} > {max_files}")
            return PolicyResult(decision=Decision.BLOCK, reasons=tuple(reasons), risk_tier="high")

        # 5 — max patch lines
        max_lines = self._policy.get("max_patch_lines", 120)
        patch_lines = len(patch.splitlines())
        if patch_lines > max_lines:
            reasons.append(f"patch too large: {patch_lines} lines > {max_lines}")
            return PolicyResult(decision=Decision.BLOCK, reasons=tuple(reasons), risk_tier="high")

        # 6 — semantic AST analysis (D1)
        semantic = _semantic_validator.validate(patch)
        if semantic.has_critical:
            for v in semantic.critical_violations:
                reasons.append(f"semantic:{v.code}: {v.message}")
            logger.warning(
                "[Policy] Semantic BLOCK — %d critical violation(s)",
                len(semantic.critical_violations),
            )
            return PolicyResult(
                decision=Decision.BLOCK,
                reasons=tuple(reasons),
                risk_tier="critical",
            )
        if semantic.has_high:
            for v in semantic.high_violations:
                reasons.append(f"semantic:{v.code}: {v.message}")
            logger.info(
                "[Policy] Semantic REVIEW — %d high violation(s)",
                len(semantic.high_violations),
            )
            return PolicyResult(
                decision=Decision.REVIEW,
                reasons=tuple(reasons),
                risk_tier="high",
            )

        # 7 — risk tier classification
        tier, tier_reasons = self._classify_risk(patch_file, patch)
        reasons.extend(tier_reasons)

        tiers = self._policy.get("risk_tiers", {})
        tier_config = tiers.get(tier, {})

        if tier_config.get("block"):
            return PolicyResult(decision=Decision.BLOCK, reasons=tuple(reasons), risk_tier=tier)

        if tier_config.get("require_human_review"):
            return PolicyResult(decision=Decision.REVIEW, reasons=tuple(reasons), risk_tier=tier)

        return PolicyResult(decision=Decision.ALLOW, reasons=tuple(reasons), risk_tier=tier)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_blocked_path(self, path: str) -> bool:
        blocked = self._policy.get("blocked_paths", [])
        return any(path.startswith(b.rstrip("/")) for b in blocked)

    def _is_allowed_path(self, path: str) -> bool:
        allowed = self._policy.get("allowed_paths", [])
        if not allowed:
            return True
        return any(path.startswith(a.rstrip("/")) for a in allowed)

    def _check_forbidden_patterns(self, patch: str) -> list[str]:
        patterns = self._policy.get("forbidden_patterns", [])
        found = []
        for pattern in patterns:
            if pattern in patch:
                found.append(pattern)
        return found

    def _classify_risk(self, patch_file: str, patch: str) -> tuple[str, list[str]]:
        """Return (tier_name, reasons) based on file path and patch content."""
        tiers = self._policy.get("risk_tiers", {})
        reasons: list[str] = []

        for tier_name in ("high", "medium", "low"):
            tier_patterns = tiers.get(tier_name, {}).get("patterns", [])
            for pattern in tier_patterns:
                if pattern in patch_file or pattern in patch:
                    reasons.append(f"risk={tier_name} matched pattern {pattern!r}")
                    return tier_name, reasons

        return "low", reasons
