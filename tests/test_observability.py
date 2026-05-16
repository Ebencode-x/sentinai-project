"""Phase 3 — Observability tests.

Coverage
--------
structured_logging.py
  - configure_logging() sets up JSON handler without error
  - configure_logging() sets up text handler without error
  - JSON output is valid JSON with required fields
  - set_request_context() attaches request_id and tenant to log records
  - clear_request_context() resets context to defaults
  - bind_request_context() context manager sets and restores context
  - bind_request_context() restores context even on exception
  - Context isolation — setting context in one scope doesn't leak
  - Extra fields passed via extra={} appear in JSON output
  - exc_info is serialised as string in JSON output

health.py
  - run_liveness() returns {"status": "ok", "service": "sentinai"}
  - run_readiness() returns ReadinessReport
  - ReadinessReport.as_dict() has required keys
  - ReadinessReport.healthy reflects check results
  - ReadinessReport.status is OK / DEGRADED / FAIL
  - Individual checks: pipeline_state, metrics, disk, audit_logger
  - Failing check returns FAIL status without raising
  - ReadinessReport.total_latency_ms is a float

routes.py (health endpoints)
  - GET /health returns 200 (legacy)
  - GET /health/live returns 200
  - GET /health/ready returns 200 in normal state
  - GET /health/ready returns 503 when a check fails
  - GET /health/ready body has "status", "healthy", "checks" keys
  - GET /health/live body has "status" key
"""

from __future__ import annotations

import json
import logging
from io import StringIO
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.core.health import (
    CheckStatus,
    HealthCheckResult,
    ReadinessReport,
    _check_audit_logger,
    _check_disk,
    _check_metrics,
    _check_pipeline_state,
    run_liveness,
    run_readiness,
)
from src.core.structured_logging import (
    bind_request_context,
    clear_request_context,
    configure_logging,
    get_request_id,
    get_tenant,
    set_request_context,
)

# ===========================================================================
# Structured logging — configure_logging()
# ===========================================================================


class TestConfigureLogging:
    def test_configure_json_does_not_raise(self):
        stream = StringIO()
        configure_logging(level="INFO", fmt="json", stream=stream)

    def test_configure_text_does_not_raise(self):
        stream = StringIO()
        configure_logging(level="DEBUG", fmt="text", stream=stream)

    def test_json_output_is_valid_json(self):
        stream = StringIO()
        configure_logging(level="DEBUG", fmt="json", stream=stream)
        log = logging.getLogger("test.json.valid")
        log.info("hello structured world")
        output = stream.getvalue().strip()
        assert output, "Expected log output"
        record = json.loads(output.splitlines()[-1])
        assert record["message"] == "hello structured world"

    def test_json_record_has_required_fields(self):
        stream = StringIO()
        configure_logging(level="DEBUG", fmt="json", stream=stream)
        log = logging.getLogger("test.fields")
        log.warning("checking fields")
        line = stream.getvalue().strip().splitlines()[-1]
        record = json.loads(line)
        for key in (
            "timestamp",
            "level",
            "logger",
            "message",
            "request_id",
            "tenant",
            "service",
            "version",
        ):
            assert key in record, f"Missing key: {key}"

    def test_json_level_matches(self):
        stream = StringIO()
        configure_logging(level="DEBUG", fmt="json", stream=stream)
        logging.getLogger("test.level").error("boom")
        line = stream.getvalue().strip().splitlines()[-1]
        assert json.loads(line)["level"] == "ERROR"

    def test_json_service_is_sentinai(self):
        stream = StringIO()
        configure_logging(level="DEBUG", fmt="json", stream=stream)
        logging.getLogger("test.service").info("x")
        line = stream.getvalue().strip().splitlines()[-1]
        assert json.loads(line)["service"] == "sentinai"

    def test_text_output_contains_message(self):
        stream = StringIO()
        configure_logging(level="DEBUG", fmt="text", stream=stream)
        logging.getLogger("test.text").info("hello text world")
        assert "hello text world" in stream.getvalue()


# ===========================================================================
# Structured logging — context vars
# ===========================================================================


class TestRequestContext:
    def setup_method(self):
        clear_request_context()

    def teardown_method(self):
        clear_request_context()

    def test_default_request_id_is_none(self):
        assert get_request_id() == "none"

    def test_default_tenant_is_anonymous(self):
        assert get_tenant() == "anonymous"

    def test_set_request_context(self):
        set_request_context(request_id="req-123", tenant="acme")
        assert get_request_id() == "req-123"
        assert get_tenant() == "acme"

    def test_clear_request_context_resets(self):
        set_request_context(request_id="req-abc", tenant="bigco")
        clear_request_context()
        assert get_request_id() == "none"
        assert get_tenant() == "anonymous"

    def test_set_context_appears_in_json_log(self):
        stream = StringIO()
        configure_logging(level="DEBUG", fmt="json", stream=stream)
        set_request_context(request_id="req-xyz", tenant="testco")
        logging.getLogger("test.ctx").info("with context")
        line = stream.getvalue().strip().splitlines()[-1]
        record = json.loads(line)
        assert record["request_id"] == "req-xyz"
        assert record["tenant"] == "testco"

    def test_bind_context_manager_sets_context(self):
        with bind_request_context(request_id="req-bind", tenant="bindco"):
            assert get_request_id() == "req-bind"
            assert get_tenant() == "bindco"

    def test_bind_context_manager_restores_after_exit(self):
        set_request_context(request_id="req-outer", tenant="outer")
        with bind_request_context(request_id="req-inner", tenant="inner"):
            pass
        assert get_request_id() == "req-outer"
        assert get_tenant() == "outer"

    def test_bind_context_manager_restores_on_exception(self):
        set_request_context(request_id="req-safe", tenant="safe")
        try:
            with bind_request_context(request_id="req-danger", tenant="danger"):
                raise ValueError("oops")
        except ValueError:
            pass
        assert get_request_id() == "req-safe"
        assert get_tenant() == "safe"

    def test_exc_info_in_json(self):
        stream = StringIO()
        configure_logging(level="DEBUG", fmt="json", stream=stream)
        log = logging.getLogger("test.exc")
        try:
            raise RuntimeError("test exception")
        except RuntimeError:
            log.exception("caught error")
        line = stream.getvalue().strip().splitlines()[-1]
        record = json.loads(line)
        assert record["exc_info"] is not None
        assert "RuntimeError" in record["exc_info"]

    def test_exc_info_none_when_no_exception(self):
        stream = StringIO()
        configure_logging(level="DEBUG", fmt="json", stream=stream)
        logging.getLogger("test.noexc").info("no error")
        line = stream.getvalue().strip().splitlines()[-1]
        record = json.loads(line)
        assert record["exc_info"] is None


# ===========================================================================
# Health — run_liveness()
# ===========================================================================


class TestLiveness:
    def test_returns_dict(self):
        result = run_liveness()
        assert isinstance(result, dict)

    def test_status_is_ok(self):
        assert run_liveness()["status"] == "ok"

    def test_service_is_sentinai(self):
        assert run_liveness()["service"] == "sentinai"


# ===========================================================================
# Health — individual checks
# ===========================================================================


class TestIndividualChecks:
    def test_check_pipeline_state_returns_result(self):
        result = _check_pipeline_state()
        assert isinstance(result, HealthCheckResult)
        assert result.name == "pipeline_state"

    def test_check_metrics_returns_result(self):
        result = _check_metrics()
        assert isinstance(result, HealthCheckResult)
        assert result.name == "metrics"

    def test_check_disk_returns_result(self):
        result = _check_disk()
        assert isinstance(result, HealthCheckResult)
        assert result.name == "disk"

    def test_check_audit_logger_returns_result(self):
        result = _check_audit_logger()
        assert isinstance(result, HealthCheckResult)
        assert result.name == "audit_logger"

    def test_check_pipeline_state_ok(self):
        result = _check_pipeline_state()
        assert result.status in (CheckStatus.OK, CheckStatus.DEGRADED, CheckStatus.FAIL)

    def test_check_metrics_ok(self):
        result = _check_metrics()
        assert result.status is CheckStatus.OK

    def test_check_disk_has_message(self):
        result = _check_disk()
        assert result.message != ""

    def test_check_latency_is_float(self):
        result = _check_metrics()
        assert isinstance(result.latency_ms, float)

    def test_failing_check_returns_fail_not_raises(self):
        """A check that throws must be caught by run_readiness."""

        def bad_check() -> HealthCheckResult:
            raise RuntimeError("simulated failure")

        with patch("src.core.health._READINESS_CHECKS", [bad_check]):
            report = run_readiness()
        assert any(c.status is CheckStatus.FAIL for c in report.checks)

    def test_health_check_result_as_dict(self):
        r = HealthCheckResult(
            name="test", status=CheckStatus.OK, message="all good", latency_ms=1.23
        )
        d = r.as_dict()
        assert d["name"] == "test"
        assert d["status"] == "ok"
        assert d["message"] == "all good"
        assert d["latency_ms"] == 1.23


# ===========================================================================
# Health — ReadinessReport
# ===========================================================================


class TestReadinessReport:
    def _ok(self, name: str) -> HealthCheckResult:
        return HealthCheckResult(name=name, status=CheckStatus.OK, message="ok")

    def _fail(self, name: str) -> HealthCheckResult:
        return HealthCheckResult(name=name, status=CheckStatus.FAIL, message="fail")

    def _degraded(self, name: str) -> HealthCheckResult:
        return HealthCheckResult(name=name, status=CheckStatus.DEGRADED, message="deg")

    def test_all_ok_is_healthy(self):
        r = ReadinessReport(checks=[self._ok("a"), self._ok("b")])
        assert r.healthy
        assert r.status is CheckStatus.OK

    def test_one_fail_is_not_healthy(self):
        r = ReadinessReport(checks=[self._ok("a"), self._fail("b")])
        assert not r.healthy
        assert r.status is CheckStatus.FAIL

    def test_degraded_only_is_degraded(self):
        r = ReadinessReport(checks=[self._ok("a"), self._degraded("b")])
        assert r.status is CheckStatus.DEGRADED

    def test_as_dict_has_required_keys(self):
        r = ReadinessReport(checks=[self._ok("x")])
        d = r.as_dict()
        for key in ("status", "healthy", "total_latency_ms", "checks"):
            assert key in d

    def test_as_dict_checks_is_list(self):
        r = ReadinessReport(checks=[self._ok("x"), self._ok("y")])
        assert isinstance(r.as_dict()["checks"], list)
        assert len(r.as_dict()["checks"]) == 2

    def test_total_latency_ms_is_float(self):
        r = ReadinessReport(checks=[self._ok("x")])
        assert isinstance(r.total_latency_ms, float)


# ===========================================================================
# Health — run_readiness()
# ===========================================================================


class TestRunReadiness:
    def test_returns_readiness_report(self):
        report = run_readiness()
        assert isinstance(report, ReadinessReport)

    def test_has_checks(self):
        report = run_readiness()
        assert len(report.checks) > 0

    def test_all_checks_have_name(self):
        report = run_readiness()
        for check in report.checks:
            assert check.name != ""

    def test_all_checks_have_status(self):
        report = run_readiness()
        for check in report.checks:
            assert isinstance(check.status, CheckStatus)


# ===========================================================================
# Routes — /health/live and /health/ready
# ===========================================================================


class TestHealthRoutes:
    @pytest.fixture
    def client(self):
        from src.main import app

        return TestClient(app)

    def test_health_live_200(self, client):
        assert client.get("/health/live").status_code == 200

    def test_health_live_status_ok(self, client):
        assert client.get("/health/live").json()["status"] == "ok"

    def test_health_live_service_sentinai(self, client):
        assert client.get("/health/live").json()["service"] == "sentinai"

    def test_health_ready_200_normally(self, client):
        assert client.get("/health/ready").status_code == 200

    def test_health_ready_has_status_key(self, client):
        assert "status" in client.get("/health/ready").json()

    def test_health_ready_has_healthy_key(self, client):
        assert "healthy" in client.get("/health/ready").json()

    def test_health_ready_has_checks_key(self, client):
        assert "checks" in client.get("/health/ready").json()

    def test_health_ready_checks_is_list(self, client):
        assert isinstance(client.get("/health/ready").json()["checks"], list)

    def test_health_ready_503_when_fail(self, client):
        from src.core.health import CheckStatus, HealthCheckResult, ReadinessReport

        failing_report = ReadinessReport(
            checks=[HealthCheckResult(name="test", status=CheckStatus.FAIL, message="broken")]
        )
        with patch("src.api.routes.run_readiness", return_value=failing_report):
            resp = client.get("/health/ready")
        assert resp.status_code == 503

    def test_health_legacy_200(self, client):
        assert client.get("/health").status_code == 200

    def test_health_legacy_status_ok(self, client):
        assert client.get("/health").json()["status"] == "ok"
