"""PR P: the patch policy runs on the live remediation path and fails closed."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from src.integrations.llm_client import StubLLMClient
from src.integrations.patch_utils import PatchRejected, normalize_repo_path, parse_single_file_patch
from src.models.events import RemediationSuggestion
from src.services import policy_engine, remediation_engine
from src.services.policy_engine import Decision, PatchPolicyEngine, PolicyResult
from src.services.remediation_engine import RemediationEngine

POLICY_YML = """\
allowed_paths:
  - src/
  - tests/
blocked_paths:
  - .github/
  - Dockerfile
forbidden_patterns:
  - "eval("
max_files_changed: 5
max_patch_lines: 120
"""


def _diff(path: str, target: str | None = None) -> str:
    return f"--- a/{path}\n+++ b/{target or path}\n@@ -1,2 +1,2 @@\n x = 1\n-y = 2\n+y = 3\n"


def _suggestion(patch: str | None) -> RemediationSuggestion:
    return RemediationSuggestion(
        summary="s",
        proposed_code_fix="c",
        proposed_config_change="",
        confidence=0.9,
        risks="r",
        proposed_patch=patch,
    )


class _FixedPolicy:
    def __init__(self, decision: Decision | None = None) -> None:
        self.decision = decision
        self.seen: list[tuple[str, int]] = []

    def check(self, patch: str, patch_file: str, files_changed: int = 1) -> PolicyResult:
        self.seen.append((patch_file, files_changed))
        if self.decision is None:
            raise RuntimeError("policy exploded")
        return PolicyResult(decision=self.decision, reasons=("test reason",), risk_tier="medium")


def _engine(
    monkeypatch: pytest.MonkeyPatch, policy: object | None = None, enforce: bool = True
) -> RemediationEngine:
    def _no_github(*args: object, **kwargs: object) -> None:
        raise RuntimeError("no github in tests")

    monkeypatch.setattr(remediation_engine, "GitHubClient", _no_github)
    return RemediationEngine(
        llm_client=StubLLMClient(),
        enforce_policy=enforce,
        policy=cast("PatchPolicyEngine | None", policy),
    )


def _real_policy(tmp_path: Path) -> PatchPolicyEngine:
    path = tmp_path / "policy.yml"
    path.write_text(POLICY_YML, encoding="utf-8")
    return PatchPolicyEngine(policy_path=path)


# ------------------------------------------------------------ engine gate


def test_gate_hands_header_path_to_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    policy = _FixedPolicy(Decision.ALLOW)
    suggestion = _suggestion(_diff("src/a.py"))
    out, needs_review = _engine(monkeypatch, policy)._apply_policy_gate(suggestion, "inc-1")
    assert out is suggestion
    assert needs_review is False
    assert policy.seen == [("src/a.py", 1)]


def test_gate_block_withholds_patch(monkeypatch: pytest.MonkeyPatch) -> None:
    policy = _FixedPolicy(Decision.BLOCK)
    suggestion = _suggestion(_diff("src/a.py"))
    out, needs_review = _engine(monkeypatch, policy)._apply_policy_gate(suggestion, "inc-1")
    assert out.proposed_patch is None
    assert (out.provider_error or "").startswith("Policy BLOCK")
    assert needs_review is False


def test_gate_review_keeps_patch_and_asks_for_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    policy = _FixedPolicy(Decision.REVIEW)
    suggestion = _suggestion(_diff("src/a.py"))
    out, needs_review = _engine(monkeypatch, policy)._apply_policy_gate(suggestion, "inc-1")
    assert out.proposed_patch == suggestion.proposed_patch
    assert needs_review is True
    assert (out.provider_error or "").startswith("Policy REVIEW")


def test_gate_withholds_when_policy_check_crashes(monkeypatch: pytest.MonkeyPatch) -> None:
    policy = _FixedPolicy(None)
    suggestion = _suggestion(_diff("src/a.py"))
    out, needs_review = _engine(monkeypatch, policy)._apply_policy_gate(suggestion, "inc-1")
    assert out.proposed_patch is None
    assert "policy check failed" in (out.provider_error or "")
    assert needs_review is False


def test_gate_withholds_when_policy_file_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(policy_engine, "_DEFAULT_POLICY", tmp_path / "missing.yml")
    engine = _engine(monkeypatch)
    out, _ = engine._apply_policy_gate(_suggestion(_diff("src/a.py")), "inc-1")
    assert out.proposed_patch is None
    assert "policy unavailable" in (out.provider_error or "")


def test_gate_off_passes_everything_through(monkeypatch: pytest.MonkeyPatch) -> None:
    policy = _FixedPolicy(Decision.BLOCK)
    suggestion = _suggestion(_diff("src/a.py"))
    out, _ = _engine(monkeypatch, policy, enforce=False)._apply_policy_gate(suggestion, "inc-1")
    assert out is suggestion
    assert policy.seen == []


def test_gate_leaves_non_diff_text_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    policy = _FixedPolicy(Decision.BLOCK)
    suggestion = _suggestion("just a code snippet, not a diff")
    out, needs_review = _engine(monkeypatch, policy)._apply_policy_gate(suggestion, "inc-1")
    assert out is suggestion
    assert needs_review is False
    assert policy.seen == []


def test_real_policy_blocks_workflow_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    engine = _engine(monkeypatch, _real_policy(tmp_path))
    suggestion = _suggestion(_diff(".github/workflows/ci.yml"))
    out, _ = engine._apply_policy_gate(suggestion, "inc-1")
    assert out.proposed_patch is None
    assert "blocked path" in (out.provider_error or "")


# ------------------------------------------------------------- patch_utils


def test_parse_returns_clean_path() -> None:
    path, _ = parse_single_file_patch(_diff("src/a.py"))
    assert path == "src/a.py"


def test_parse_accepts_headers_without_prefix() -> None:
    diff = _diff("src/a.py").replace("a/src", "src").replace("b/src", "src")
    path, _ = parse_single_file_patch(diff)
    assert path == "src/a.py"


def test_parse_rejects_headers_naming_different_files() -> None:
    with pytest.raises(PatchRejected):
        parse_single_file_patch(_diff("src/a.py", ".github/workflows/ci.yml"))


def test_parse_rejects_dot_dot_in_header() -> None:
    with pytest.raises(PatchRejected):
        parse_single_file_patch(_diff("src/../.github/ci.yml"))


@pytest.mark.parametrize(
    "raw", ["", "/etc/passwd", "src/../x", "./src/x", "src//x", "src\\x", "src/x/"]
)
def test_normalize_rejects_unsafe_paths(raw: str) -> None:
    with pytest.raises(PatchRejected):
        normalize_repo_path(raw)


def test_normalize_keeps_plain_path() -> None:
    assert normalize_repo_path("src/x.py") == "src/x.py"


# ------------------------------------------------------------ policy engine


def test_policy_blocks_patch_file_that_differs_from_header(tmp_path: Path) -> None:
    result = _real_policy(tmp_path).check(
        patch=_diff(".github/workflows/ci.yml"), patch_file="docs/readme.md"
    )
    assert result.blocked
    assert any("does not match" in r for r in result.reasons)


def test_policy_blocks_dot_dot_patch_file(tmp_path: Path) -> None:
    result = _real_policy(tmp_path).check(
        patch=_diff("src/a.py"), patch_file="src/../.github/ci.yml"
    )
    assert result.blocked
    assert any("unsafe" in r for r in result.reasons)


def test_policy_allows_matching_clean_patch(tmp_path: Path) -> None:
    result = _real_policy(tmp_path).check(patch=_diff("src/a.py"), patch_file="src/a.py")
    assert not result.blocked


def test_require_policy_raises_when_file_is_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        PatchPolicyEngine(policy_path=tmp_path / "missing.yml", require_policy=True)
