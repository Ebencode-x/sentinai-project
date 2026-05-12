"""B3 tests — ResourceLimitEnforcer."""

from __future__ import annotations

import pytest

from src.services.resource_enforcer import (
    _HARD_MAX_CPUS,
    _HARD_MAX_MEMORY_MB,
    _HARD_MAX_TIMEOUT_S,
    _HARD_MAX_TMPFS_MB,
    _MIN_MEMORY_MB,
    _MIN_TIMEOUT_S,
    ResourceLimitEnforcer,
)
from src.services.sandbox_config import SandboxConfig


def _valid_config(**overrides) -> SandboxConfig:
    """Return a known-good config with optional field overrides."""
    base = dict(
        memory_mb=256,
        cpus=0.5,
        timeout_seconds=120,
        tmpfs_size_mb=64,
        network="none",
        read_only_root=True,
        user="sentinai",
        security_opt=["no-new-privileges"],
        drop_capabilities=["ALL"],
    )
    base.update(overrides)
    return SandboxConfig(**base)


@pytest.fixture
def enforcer() -> ResourceLimitEnforcer:
    return ResourceLimitEnforcer()


class TestValidConfig:
    def test_valid_config_passes(self, enforcer):
        result = enforcer.validate(_valid_config())
        assert result.valid is True
        assert result.violations == ()

    def test_summary_on_valid(self, enforcer):
        result = enforcer.validate(_valid_config())
        assert "valid" in result.summary.lower()


class TestMemoryLimits:
    def test_memory_below_minimum_fails(self, enforcer):
        result = enforcer.validate(_valid_config(memory_mb=_MIN_MEMORY_MB - 1))
        assert not result.valid
        assert any("below minimum" in v for v in result.violations)

    def test_memory_at_minimum_passes(self, enforcer):
        result = enforcer.validate(_valid_config(memory_mb=_MIN_MEMORY_MB))
        assert result.valid

    def test_memory_exceeds_ceiling_fails(self, enforcer):
        result = enforcer.validate(_valid_config(memory_mb=_HARD_MAX_MEMORY_MB + 1))
        assert not result.valid
        assert any("hard ceiling" in v for v in result.violations)

    def test_memory_at_ceiling_passes(self, enforcer):
        result = enforcer.validate(_valid_config(memory_mb=_HARD_MAX_MEMORY_MB))
        assert result.valid


class TestCpuLimits:
    def test_cpus_zero_fails(self, enforcer):
        result = enforcer.validate(_valid_config(cpus=0.0))
        assert not result.valid
        assert any("cpus" in v for v in result.violations)

    def test_cpus_negative_fails(self, enforcer):
        result = enforcer.validate(_valid_config(cpus=-1.0))
        assert not result.valid

    def test_cpus_exceeds_ceiling_fails(self, enforcer):
        result = enforcer.validate(_valid_config(cpus=_HARD_MAX_CPUS + 0.1))
        assert not result.valid
        assert any("hard ceiling" in v for v in result.violations)

    def test_cpus_at_ceiling_passes(self, enforcer):
        result = enforcer.validate(_valid_config(cpus=_HARD_MAX_CPUS))
        assert result.valid


class TestTimeoutLimits:
    def test_timeout_below_minimum_fails(self, enforcer):
        result = enforcer.validate(_valid_config(timeout_seconds=_MIN_TIMEOUT_S - 1))
        assert not result.valid
        assert any("timeout" in v for v in result.violations)

    def test_timeout_at_minimum_passes(self, enforcer):
        result = enforcer.validate(_valid_config(timeout_seconds=_MIN_TIMEOUT_S))
        assert result.valid

    def test_timeout_exceeds_ceiling_fails(self, enforcer):
        result = enforcer.validate(_valid_config(timeout_seconds=_HARD_MAX_TIMEOUT_S + 1))
        assert not result.valid

    def test_timeout_at_ceiling_passes(self, enforcer):
        result = enforcer.validate(_valid_config(timeout_seconds=_HARD_MAX_TIMEOUT_S))
        assert result.valid


class TestTmpfsLimits:
    def test_tmpfs_exceeds_ceiling_fails(self, enforcer):
        result = enforcer.validate(_valid_config(tmpfs_size_mb=_HARD_MAX_TMPFS_MB + 1))
        assert not result.valid
        assert any("tmpfs" in v for v in result.violations)

    def test_tmpfs_at_ceiling_passes(self, enforcer):
        result = enforcer.validate(_valid_config(tmpfs_size_mb=_HARD_MAX_TMPFS_MB))
        assert result.valid


class TestSecurityConstraints:
    def test_network_not_none_fails(self, enforcer):
        result = enforcer.validate(_valid_config(network="bridge"))
        assert not result.valid
        assert any("network" in v for v in result.violations)

    def test_read_only_false_fails(self, enforcer):
        result = enforcer.validate(_valid_config(read_only_root=False))
        assert not result.valid
        assert any("read_only_root" in v for v in result.violations)

    def test_root_user_fails(self, enforcer):
        result = enforcer.validate(_valid_config(user="root"))
        assert not result.valid
        assert any("non-root" in v for v in result.violations)

    def test_empty_user_fails(self, enforcer):
        result = enforcer.validate(_valid_config(user=""))
        assert not result.valid

    def test_missing_no_new_privileges_fails(self, enforcer):
        result = enforcer.validate(_valid_config(security_opt=[]))
        assert not result.valid
        assert any("no-new-privileges" in v for v in result.violations)

    def test_missing_cap_drop_all_fails(self, enforcer):
        result = enforcer.validate(_valid_config(drop_capabilities=[]))
        assert not result.valid
        assert any("ALL" in v for v in result.violations)


class TestMultipleViolations:
    def test_all_violations_collected(self, enforcer):
        bad = _valid_config(
            network="bridge",
            read_only_root=False,
            user="root",
            memory_mb=_HARD_MAX_MEMORY_MB + 1,
        )
        result = enforcer.validate(bad)
        assert not result.valid
        assert len(result.violations) >= 3

    def test_summary_contains_violations(self, enforcer):
        bad = _valid_config(network="bridge", read_only_root=False)
        result = enforcer.validate(bad)
        assert "violation" in result.summary.lower()


class TestEnforceRaises:
    def test_enforce_raises_on_invalid(self, enforcer):
        with pytest.raises(ValueError, match="violation"):
            enforcer.enforce(_valid_config(network="bridge"))

    def test_enforce_silent_on_valid(self, enforcer):
        enforcer.enforce(_valid_config())  # must not raise


class TestSandboxRunnerIntegration:
    def test_enforcer_blocks_bad_config(self, enforcer):
        bad = _valid_config(memory_mb=_HARD_MAX_MEMORY_MB + 100, network="bridge")
        result = enforcer.validate(bad)
        assert not result.valid
