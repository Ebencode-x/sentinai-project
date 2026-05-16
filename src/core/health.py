"""Phase 3 — Health check subsystem.

Exposes two standard Kubernetes-style probes:

/health/live   (liveness)
    Is the process alive?  Returns 200 immediately.
    Kubernetes restarts the pod if this fails.

/health/ready  (readiness)
    Is the service ready to serve traffic?
    Runs lightweight checks on every critical dependency.
    Returns 200 only when ALL checks pass.
    Kubernetes stops sending traffic if this fails.

Check catalogue
---------------
CheckName           What it verifies
-----------         ----------------
pipeline_state      app_state is initialised and reachable
metrics             MetricsCollector is recording (smoke test)
disk                /tmp has > MIN_FREE_MB of space
audit_logger        AuditLogger singleton is reachable
llm_client          LLM client can be constructed without error

Adding new checks
-----------------
Implement a function with signature ``() -> HealthCheckResult`` and
register it in ``_READINESS_CHECKS``.
"""

from __future__ import annotations

import logging
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

logger = logging.getLogger(__name__)

_MIN_FREE_MB = 100  # minimum free disk space in /tmp


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


class CheckStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    FAIL = "fail"


@dataclass(frozen=True)
class HealthCheckResult:
    name: str
    status: CheckStatus
    message: str = ""
    latency_ms: float = 0.0

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "status": str(self.status),
            "message": self.message,
            "latency_ms": round(self.latency_ms, 2),
        }


@dataclass
class ReadinessReport:
    """Aggregated result of all readiness checks."""

    checks: list[HealthCheckResult] = field(default_factory=list)
    started_at: float = field(default_factory=time.monotonic)

    @property
    def healthy(self) -> bool:
        return all(c.status is CheckStatus.OK for c in self.checks)

    @property
    def status(self) -> CheckStatus:
        if all(c.status is CheckStatus.OK for c in self.checks):
            return CheckStatus.OK
        if any(c.status is CheckStatus.FAIL for c in self.checks):
            return CheckStatus.FAIL
        return CheckStatus.DEGRADED

    @property
    def total_latency_ms(self) -> float:
        return round((time.monotonic() - self.started_at) * 1000, 2)

    def as_dict(self) -> dict:
        return {
            "status": str(self.status),
            "healthy": self.healthy,
            "total_latency_ms": self.total_latency_ms,
            "checks": [c.as_dict() for c in self.checks],
        }


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _check_pipeline_state() -> HealthCheckResult:
    """Verify app_state is initialised."""
    start = time.monotonic()
    try:
        from src.core.state import app_state  # noqa: PLC0415

        _ = app_state.stats_snapshot()
        return HealthCheckResult(
            name="pipeline_state",
            status=CheckStatus.OK,
            message="app_state reachable",
            latency_ms=(time.monotonic() - start) * 1000,
        )
    except Exception as exc:  # noqa: BLE001
        return HealthCheckResult(
            name="pipeline_state",
            status=CheckStatus.FAIL,
            message=f"app_state error: {exc}",
            latency_ms=(time.monotonic() - start) * 1000,
        )


def _check_metrics() -> HealthCheckResult:
    """Verify MetricsCollector is functional."""
    start = time.monotonic()
    try:
        from src.core.metrics import metrics  # noqa: PLC0415

        snap = metrics.snapshot()
        assert isinstance(snap, dict), "snapshot() must return dict"
        return HealthCheckResult(
            name="metrics",
            status=CheckStatus.OK,
            message="MetricsCollector functional",
            latency_ms=(time.monotonic() - start) * 1000,
        )
    except Exception as exc:  # noqa: BLE001
        return HealthCheckResult(
            name="metrics",
            status=CheckStatus.FAIL,
            message=f"metrics error: {exc}",
            latency_ms=(time.monotonic() - start) * 1000,
        )


def _check_disk() -> HealthCheckResult:
    """Verify temp directory has sufficient free space."""
    import tempfile

    start = time.monotonic()
    try:
        tmp_dir = tempfile.gettempdir()
        usage = shutil.disk_usage(tmp_dir)
        free_mb = usage.free / (1024 * 1024)
        status = CheckStatus.OK if free_mb >= _MIN_FREE_MB else CheckStatus.DEGRADED
        return HealthCheckResult(
            name="disk",
            status=status,
            message=f"{free_mb:.0f} MB free in {tmp_dir} (min {_MIN_FREE_MB} MB)",
            latency_ms=(time.monotonic() - start) * 1000,
        )
    except Exception as exc:  # noqa: BLE001
        return HealthCheckResult(
            name="disk",
            status=CheckStatus.FAIL,
            message=f"disk check error: {exc}",
            latency_ms=(time.monotonic() - start) * 1000,
        )


def _check_audit_logger() -> HealthCheckResult:
    """Verify AuditLogger singleton is reachable."""
    start = time.monotonic()
    try:
        from src.core.audit import audit_logger  # noqa: PLC0415

        assert audit_logger is not None
        return HealthCheckResult(
            name="audit_logger",
            status=CheckStatus.OK,
            message="AuditLogger reachable",
            latency_ms=(time.monotonic() - start) * 1000,
        )
    except Exception as exc:  # noqa: BLE001
        return HealthCheckResult(
            name="audit_logger",
            status=CheckStatus.FAIL,
            message=f"audit_logger error: {exc}",
            latency_ms=(time.monotonic() - start) * 1000,
        )


def _check_llm_client() -> HealthCheckResult:
    """Verify LLM client can be constructed."""
    start = time.monotonic()
    try:
        from src.integrations.llm_client import build_llm_client  # noqa: PLC0415

        client = build_llm_client()
        assert client is not None
        return HealthCheckResult(
            name="llm_client",
            status=CheckStatus.OK,
            message="LLM client constructable",
            latency_ms=(time.monotonic() - start) * 1000,
        )
    except Exception as exc:  # noqa: BLE001
        # LLM being unavailable is DEGRADED, not FAIL — pipeline has fallback
        return HealthCheckResult(
            name="llm_client",
            status=CheckStatus.DEGRADED,
            message=f"LLM client degraded: {exc}",
            latency_ms=(time.monotonic() - start) * 1000,
        )


# ---------------------------------------------------------------------------
# Check registry
# ---------------------------------------------------------------------------

_READINESS_CHECKS: list[Callable[[], HealthCheckResult]] = [
    _check_pipeline_state,
    _check_metrics,
    _check_disk,
    _check_audit_logger,
    _check_llm_client,
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_liveness() -> dict:
    """Liveness probe — always fast, never fails unless process is broken."""
    return {"status": "ok", "service": "sentinai"}


def run_readiness() -> ReadinessReport:
    """Run all registered readiness checks and return aggregated report."""
    report = ReadinessReport()
    for check_fn in _READINESS_CHECKS:
        try:
            result = check_fn()
        except Exception as exc:  # noqa: BLE001
            result = HealthCheckResult(
                name=check_fn.__name__,
                status=CheckStatus.FAIL,
                message=f"Unhandled error in check: {exc}",
            )
        report.checks.append(result)
        if result.status is not CheckStatus.OK:
            logger.warning(
                "[Health] Check '%s' status=%s: %s",
                result.name,
                result.status,
                result.message,
            )
    return report
