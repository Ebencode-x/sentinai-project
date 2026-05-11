"""Tests for PatchPolicyEngine — A1."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.services.policy_engine import Decision, PatchPolicyEngine


@pytest.fixture()
def policy_file(tmp_path: Path) -> Path:
    policy = {
        "allowed_paths": ["src/", "tests/"],
        "blocked_paths": [".env", "secrets/", ".github/"],
        "max_files_changed": 5,
        "max_patch_lines": 120,
        "forbidden_patterns": ["shell=True", "eval(", "exec("],
        "require_tests_pass": True,
        "risk_tiers": {
            "high": {
                "block": True,
                "patterns": ["auth", "token", "password", "secret"],
            },
            "medium": {
                "require_human_review": True,
                "patterns": ["src/services/", "src/core/"],
            },
            "low": {
                "auto_pr": True,
                "patterns": ["tests/", ".md"],
            },
        },
    }
    p = tmp_path / "sentinai-policy.yml"
    p.write_text(yaml.dump(policy), encoding="utf-8")
    return p


@pytest.fixture()
def engine(policy_file: Path) -> PatchPolicyEngine:
    return PatchPolicyEngine(policy_path=policy_file)


# ── Path checks ────────────────────────────────────────────────────────────


class TestPathPolicy:
    def test_allowed_path_passes(self, engine: PatchPolicyEngine) -> None:
        result = engine.check("- old\n+ new\n", "src/services/handler.py")
        assert not result.blocked

    def test_blocked_path_blocked(self, engine: PatchPolicyEngine) -> None:
        result = engine.check("- old\n+ new\n", ".env")
        assert result.blocked
        assert any("blocked path" in r for r in result.reasons)

    def test_path_not_in_allowed_blocked(self, engine: PatchPolicyEngine) -> None:
        result = engine.check("- old\n+ new\n", "infra/k8s.yml")
        assert result.blocked
        assert any("allowed_paths" in r for r in result.reasons)

    def test_github_dir_blocked(self, engine: PatchPolicyEngine) -> None:
        result = engine.check("- old\n+ new\n", ".github/workflows/ci.yml")
        assert result.blocked


# ── Forbidden patterns ─────────────────────────────────────────────────────


class TestForbiddenPatterns:
    def test_shell_true_blocked(self, engine: PatchPolicyEngine) -> None:
        patch = "+    subprocess.run(cmd, shell=True)\n"
        result = engine.check(patch, "src/services/runner.py")
        assert result.blocked
        assert any("shell=True" in r for r in result.reasons)

    def test_eval_blocked(self, engine: PatchPolicyEngine) -> None:
        patch = "+    result = eval(user_input)\n"
        result = engine.check(patch, "src/services/handler.py")
        assert result.blocked

    def test_exec_blocked(self, engine: PatchPolicyEngine) -> None:
        patch = "+    exec(code)\n"
        result = engine.check(patch, "src/services/handler.py")
        assert result.blocked

    def test_clean_patch_not_blocked(self, engine: PatchPolicyEngine) -> None:
        patch = "-    x = 1\n+    x = 2\n"
        result = engine.check(patch, "src/services/handler.py")
        assert not result.blocked


# ── Size limits ────────────────────────────────────────────────────────────


class TestSizeLimits:
    def test_too_many_files_blocked(self, engine: PatchPolicyEngine) -> None:
        result = engine.check("- a\n+ b\n", "src/services/x.py", files_changed=6)
        assert result.blocked
        assert any("too many files" in r for r in result.reasons)

    def test_patch_too_large_blocked(self, engine: PatchPolicyEngine) -> None:
        big_patch = "\n".join(f"+ line {i}" for i in range(200))
        result = engine.check(big_patch, "src/services/x.py")
        assert result.blocked
        assert any("patch too large" in r for r in result.reasons)

    def test_patch_within_limit_passes(self, engine: PatchPolicyEngine) -> None:
        small_patch = "\n".join(f"+ line {i}" for i in range(10))
        result = engine.check(small_patch, "src/services/x.py")
        assert not result.blocked


# ── Risk tiers ─────────────────────────────────────────────────────────────


class TestRiskTiers:
    def test_auth_file_blocked(self, engine: PatchPolicyEngine) -> None:
        result = engine.check("- old\n+ new\n", "src/api/auth.py")
        assert result.blocked
        assert result.risk_tier == "high"

    def test_service_file_requires_review(self, engine: PatchPolicyEngine) -> None:
        result = engine.check("- old\n+ new\n", "src/services/watcher.py")
        assert result.requires_review
        assert result.risk_tier == "medium"

    def test_test_file_auto_allowed(self, engine: PatchPolicyEngine) -> None:
        result = engine.check("- old\n+ new\n", "tests/test_watcher.py")
        assert result.decision == Decision.ALLOW
        assert result.risk_tier == "low"

    def test_password_in_patch_blocked(self, engine: PatchPolicyEngine) -> None:
        patch = "+    password = get_password()\n"
        result = engine.check(patch, "src/services/handler.py")
        assert result.blocked
        assert result.risk_tier == "high"


# ── Reload ─────────────────────────────────────────────────────────────────


class TestReload:
    def test_reload_picks_up_changes(self, tmp_path: Path) -> None:
        p = tmp_path / "policy.yml"
        p.write_text(
            yaml.dump({"allowed_paths": ["src/"], "blocked_paths": []}),
            encoding="utf-8",
        )
        engine = PatchPolicyEngine(policy_path=p)
        assert not engine.check("+ x\n", "src/x.py").blocked

        p.write_text(
            yaml.dump({"allowed_paths": [], "blocked_paths": ["src/"]}),
            encoding="utf-8",
        )
        engine.reload()
        assert engine.check("+ x\n", "src/x.py").blocked
