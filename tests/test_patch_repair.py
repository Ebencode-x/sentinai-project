"""PR A: hunk headers are recomputed and hunks are located by content."""

from __future__ import annotations

from typing import cast

import pytest

from src.integrations.llm_client import StubLLMClient
from src.integrations.patch_utils import (
    PatchRejected,
    apply_verified,
    canonicalize_patch,
    parse_single_file_patch,
)
from src.models.events import RemediationSuggestion
from src.services import remediation_engine
from src.services.policy_engine import Decision, PatchPolicyEngine, PolicyResult
from src.services.remediation_engine import RemediationEngine

LINES = "".join(f"l{i}\n" for i in range(1, 21))


def _diff(*hunks: str, path: str = "src/a.py") -> str:
    return f"--- a/{path}\n+++ b/{path}\n" + "".join(hunks)


def _apply(original: str, diff: str) -> str:
    _, patch_set = parse_single_file_patch(diff)
    return apply_verified(original, patch_set)


# ------------------------------------------------------------ header repair


def test_header_with_too_small_counts_no_longer_drops_changes() -> None:
    hunk = "@@ -1,3 +1,3 @@\n a\n-b\n+B\n c\n-d\n+D\n e\n"
    assert _apply("a\nb\nc\nd\ne\n", _diff(hunk)) == "a\nB\nc\nD\ne\n"


def test_header_with_too_large_counts_is_repaired() -> None:
    hunk = "@@ -1,9 +1,9 @@\n a\n-b\n+B\n c\n"
    assert _apply("a\nb\nc\n", _diff(hunk)) == "a\nB\nc\n"


def test_header_without_counts_is_repaired() -> None:
    hunk = "@@ -1 +1 @@\n a\n-b\n+B\n c\n"
    assert _apply("a\nb\nc\n", _diff(hunk)) == "a\nB\nc\n"


def test_canonical_header_has_real_counts_and_keeps_function_context() -> None:
    hunk = "@@ -1,2 +1,2 @@ def f():\n a\n-b\n+B\n c\n"
    assert "@@ -1,3 +1,3 @@ def f():" in canonicalize_patch(_diff(hunk))


def test_canonicalize_is_idempotent() -> None:
    hunk = "@@ -1,3 +1,3 @@\n a\n-b\n+B\n c\n-d\n+D\n e\n"
    once = canonicalize_patch(_diff(hunk))
    assert canonicalize_patch(once) == once


def test_blank_line_inside_a_hunk_is_a_blank_context_line() -> None:
    hunk = "@@ -1,3 +1,3 @@\n a\n\n-b\n+B\n"
    assert _apply("a\n\nb\n", _diff(hunk)) == "a\n\nB\n"


def test_blank_separators_between_and_after_hunks_are_ignored() -> None:
    h1 = "@@ -1,3 +1,3 @@\n l1\n-l2\n+L2\n l3\n"
    h2 = "@@ -14,3 +14,3 @@\n l14\n-l15\n+L15\n l16\n"
    expected = LINES.replace("l2\n", "L2\n").replace("l15\n", "L15\n")
    assert _apply(LINES, _diff(h1, "\n", h2, "\n\n")) == expected


def test_hunk_line_without_marker_is_rejected() -> None:
    with pytest.raises(PatchRejected, match="marker"):
        parse_single_file_patch(_diff("@@ -1,2 +1,2 @@\n a\nb = 1\n"))


def test_diff_without_hunks_is_rejected() -> None:
    with pytest.raises(PatchRejected, match="no hunks"):
        parse_single_file_patch("--- a/src/a.py\n+++ b/src/a.py\n")


def test_malformed_hunk_header_is_rejected() -> None:
    with pytest.raises(PatchRejected, match="malformed"):
        parse_single_file_patch(_diff("@@ somewhere @@\n a\n-b\n+B\n"))


# ----------------------------------------------------- content based search


def test_wrong_line_number_is_found_by_content() -> None:
    hunk = "@@ -1,3 +1,3 @@\n l9\n-l10\n+L10\n l11\n"
    assert _apply(LINES, _diff(hunk)) == LINES.replace("l10\n", "L10\n")


def test_ambiguous_block_with_wrong_number_is_rejected() -> None:
    hunk = "@@ -9,2 +9,2 @@\n x\n-y\n+Y\n"
    with pytest.raises(PatchRejected, match="ambiguous"):
        _apply("x\ny\nq\nx\ny\n", _diff(hunk))


def test_declared_position_wins_when_it_matches() -> None:
    hunk = "@@ -4,2 +4,2 @@\n x\n-y\n+Y\n"
    assert _apply("x\ny\nq\nx\ny\n", _diff(hunk)) == "x\ny\nq\nx\nY\n"


def test_block_that_is_not_in_the_file_is_rejected() -> None:
    hunk = "@@ -1,2 +1,2 @@\n zz\n-yy\n+Y\n"
    with pytest.raises(PatchRejected, match="does not match"):
        _apply(LINES, _diff(hunk))


def test_hunks_out_of_order_are_rejected() -> None:
    first = "@@ -9,3 +9,3 @@\n l9\n-l10\n+L10\n l11\n"
    second = "@@ -2,3 +2,3 @@\n l2\n-l3\n+L3\n l4\n"
    with pytest.raises(PatchRejected):
        _apply(LINES, _diff(first, second))


def test_insertion_without_context_is_allowed_at_the_end() -> None:
    assert _apply("a\nb\nc\n", _diff("@@ -3,0 +4,1 @@\n+X\n")) == "a\nb\nc\nX\n"


def test_single_hunk_insertion_at_line_zero_is_treated_as_file_creation() -> None:
    # unidiff cannot tell this from a new file, so it is rejected on purpose
    with pytest.raises(PatchRejected, match="creating or deleting"):
        _apply("a\nb\nc\n", _diff("@@ -0,0 +1,1 @@\n+X\n"))


def test_insertion_at_the_start_works_when_combined_with_another_hunk() -> None:
    first = "@@ -0,0 +1,1 @@\n+X\n"
    second = "@@ -2,3 +3,3 @@\n b\n-c\n+C\n d\n"
    assert _apply("a\nb\nc\nd\n", _diff(first, second)) == "X\na\nb\nC\nd\n"


def test_insertion_without_context_in_the_middle_is_rejected() -> None:
    with pytest.raises(PatchRejected, match="no context"):
        _apply("a\nb\nc\n", _diff("@@ -1,0 +2,1 @@\n+X\n"))


# ----------------------------------------------------------------- the gate


class _Recorder:
    def __init__(self) -> None:
        self.patches: list[str] = []

    def check(self, patch: str, patch_file: str, files_changed: int = 1) -> PolicyResult:
        self.patches.append(patch)
        return PolicyResult(decision=Decision.ALLOW, reasons=(), risk_tier="low")


def test_gate_hands_the_canonical_diff_to_policy_and_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_github(*args: object, **kwargs: object) -> None:
        raise RuntimeError("no github in tests")

    monkeypatch.setattr(remediation_engine, "GitHubClient", _no_github)
    recorder = _Recorder()
    engine = RemediationEngine(
        llm_client=StubLLMClient(),
        policy=cast("PatchPolicyEngine | None", recorder),
    )
    raw = _diff("@@ -1,3 +1,3 @@\n a\n-b\n+B\n c\n-d\n+D\n e\n")
    suggestion = RemediationSuggestion(
        summary="s",
        proposed_code_fix="c",
        proposed_config_change="",
        confidence=0.9,
        risks="r",
        proposed_patch=raw,
    )
    out, needs_review = engine._apply_policy_gate(suggestion, "inc-1")
    assert needs_review is False
    assert out.proposed_patch == canonicalize_patch(raw)
    assert recorder.patches == [out.proposed_patch]
    assert "@@ -1,5 +1,5 @@" in recorder.patches[0]
