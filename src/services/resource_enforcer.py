"""Resource Limit Enforcer — B3.

Validates sandbox resource limits before any Docker container is launched.
Fails fast with a clear error if a limit is violated or misconfigured.
All violations are collected and reported together (not one-by-one).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from src.services.sandbox_config import SandboxConfig

logger = logging.getLogger(__name__)

_HARD_MAX_MEMORY_MB: int = int(os.getenv("SENTINAI_SANDBOX_MAX_MEMORY_MB", "1024"))
_HARD_MAX_CPUS: float = float(os.getenv("SENTINAI_SANDBOX_MAX_CPUS", "2.0"))
_HARD_MAX_TIMEOUT_S: int = int(os.getenv("SENTINAI_SANDBOX_MAX_TIMEOUT_S", "300"))
_HARD_MAX_TMPFS_MB: int = int(os.getenv("SENTINAI_SANDBOX_MAX_TMPFS_MB", "256"))
_MIN_MEMORY_MB: int = 64
_MIN_TIMEOUT_S: int = 10


@dataclass(frozen=True)
class EnforcementResult:
    valid: bool
    violations: tuple[str, ...]

    @property
    def summary(self) -> str:
        if self.valid:
            return "All resource limits valid."
        return "Resource limit violations: " + "; ".join(self.violations)


class ResourceLimitEnforcer:
    """Validate SandboxConfig resource limits before container launch."""

    def validate(self, config: SandboxConfig) -> EnforcementResult:
        violations: list[str] = []

        if config.memory_mb < _MIN_MEMORY_MB:
            violations.append(f"memory_mb={config.memory_mb} below minimum {_MIN_MEMORY_MB}MB")
        if config.memory_mb > _HARD_MAX_MEMORY_MB:
            violations.append(
                f"memory_mb={config.memory_mb} exceeds hard ceiling {_HARD_MAX_MEMORY_MB}MB"
            )
        if config.cpus <= 0:
            violations.append(f"cpus={config.cpus} must be > 0")
        if config.cpus > _HARD_MAX_CPUS:
            violations.append(f"cpus={config.cpus} exceeds hard ceiling {_HARD_MAX_CPUS}")
        if config.timeout_seconds < _MIN_TIMEOUT_S:
            violations.append(
                f"timeout_seconds={config.timeout_seconds} below minimum {_MIN_TIMEOUT_S}s"
            )
        if config.timeout_seconds > _HARD_MAX_TIMEOUT_S:
            violations.append(
                f"timeout_seconds={config.timeout_seconds} exceeds hard ceiling "
                f"{_HARD_MAX_TIMEOUT_S}s"
            )
        if config.tmpfs_size_mb > _HARD_MAX_TMPFS_MB:
            violations.append(
                f"tmpfs_size_mb={config.tmpfs_size_mb} exceeds hard ceiling {_HARD_MAX_TMPFS_MB}MB"
            )
        if config.network != "none":
            violations.append(f"network={config.network!r} — only 'none' is permitted in sandbox")
        if not config.read_only_root:
            violations.append("read_only_root=False — sandbox root FS must be read-only")
        if not config.user or config.user == "root":
            violations.append(f"user={config.user!r} — sandbox must run as non-root user")
        if "no-new-privileges" not in config.security_opt:
            violations.append(
                "security_opt missing 'no-new-privileges' — required for sandbox hardening"
            )
        if "ALL" not in config.drop_capabilities:
            violations.append(
                "drop_capabilities missing 'ALL' — all Linux capabilities must be dropped"
            )

        valid = len(violations) == 0
        if not valid:
            logger.warning("[Enforcer] %d violation(s): %s", len(violations), violations)
        else:
            logger.debug("[Enforcer] All limits valid for image=%s", config.image)
        return EnforcementResult(valid=valid, violations=tuple(violations))

    def enforce(self, config: SandboxConfig) -> None:
        """Validate and raise ValueError if any limit is violated."""
        result = self.validate(config)
        if not result.valid:
            raise ValueError(result.summary)
