"""Output flow verification — C4.

Confirms that pipeline output reaches its destination without manual
intervention across all execution paths:

  1. Audit JSONL written to disk — real file I/O, not a mock.
  2. Telemetry fields carry accurate values (not just presence checks).
  3. Multi-incident flow — sequential runs produce isolated audit entries.
  4. Failure path — audit is always written, even when pipeline fails.

No real LLM, Docker, or GitHub calls are made.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.core.audit import AuditLogger
from src.models.events import LogIncident, RemediationSuggestion
from src.services.pipeline import PipelineResult, RemediationPipeline

# ---------------------------------------------------------------------------
# Shared factories — identical style to C3 for consistency
# ---------------------------------------------------------------------------


def _make_incident(
    incident_id: str = "c4-incident-001",
    *,
    trigger_line: str = "ERROR db connection refused at 192.168.0.1",
    stacktrace: str = (
        "Traceback (most recent call last):\n"
        '  File "app.py", line 10, in run\n'
        "  ConnectionRefusedError: [Errno 111] Connection refused"
    ),
    context: str = "INFO worker starting\nINFO connecting",
) -> LogIncident:
    return LogIncident(
        incident_id=incident_id,
        detected_at_utc=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
        severity="critical",
        trigger_line=trigger_line,
        stacktrace=stacktrace,
        context_before_error=context,
    )


def _make_suggestion(**kwargs) -> RemediationSuggestion:
    defaults = dict(
        summary="Add retry with backoff",
        proposed_code_fix="retry()",
        proposed_config_change="none",
        confidence=0.88,
        risks="Low",
        source="stub",
        proposed_patch="- old\n+ new\n",
        patch_file="src/app.py",
        test_guidance="run test_app.py",
    )
    defaults.update(kwargs)
    return RemediationSuggestion(**defaults)


def _build_pipeline(tmp_path: Path, *, dry_run: bool = True) -> RemediationPipeline:
    """Build a pipeline with all external I/O stubbed."""
    with (
        patch("src.services.pipeline.build_llm_client"),
        patch("src.services.pipeline.GitHubClient", side_effect=RuntimeError("no github")),
        patch(
            "src.services.pipeline.SandboxedPatchRunner",
            side_effect=RuntimeError("no docker"),
        ),
    ):
        return RemediationPipeline(project_root=tmp_path, dry_run=dry_run)


def _mock_patch_run(pipeline: RemediationPipeline) -> tuple:
    """Return context managers for runner.apply + runner.run_tests."""
    apply_mock = patch.object(
        pipeline._runner,
        "apply",
        return_value=MagicMock(success=True, error=None),
    )
    tests_mock = patch.object(
        pipeline._runner,
        "run_tests",
        return_value=MagicMock(success=True, output="1 passed"),
    )
    return apply_mock, tests_mock


# ---------------------------------------------------------------------------
# C4-1 — Audit JSONL written to disk
# ---------------------------------------------------------------------------


class TestAuditOutputToDisk:
    """Verify that pipeline writes a valid JSONL entry to the audit file."""

    def test_audit_file_created_on_first_run(self, tmp_path: Path):
        """Audit log is created automatically — no manual setup needed."""
        log_path = tmp_path / "logs" / "sentinai-audit.jsonl"
        audit = AuditLogger(log_path=log_path)

        pipeline = _build_pipeline(tmp_path)
        pipeline._audit = audit  # inject isolated logger

        incident = _make_incident()
        apply_ctx, tests_ctx = _mock_patch_run(pipeline)

        with patch.object(pipeline._engine, "suggest_fix", return_value=_make_suggestion()):
            with apply_ctx, tests_ctx:
                pipeline.run(incident)

        assert log_path.exists(), "Audit JSONL file was not created"

    def test_audit_entry_is_valid_json(self, tmp_path: Path):
        """Every line in the audit log must be valid JSON."""
        log_path = tmp_path / "logs" / "sentinai-audit.jsonl"
        audit = AuditLogger(log_path=log_path)

        pipeline = _build_pipeline(tmp_path)
        pipeline._audit = audit

        incident = _make_incident()
        apply_ctx, tests_ctx = _mock_patch_run(pipeline)

        with patch.object(pipeline._engine, "suggest_fix", return_value=_make_suggestion()):
            with apply_ctx, tests_ctx:
                pipeline.run(incident)

        lines = [ln.strip() for ln in log_path.read_text().splitlines() if ln.strip()]
        assert lines, "Audit file is empty"
        for line in lines:
            parsed = json.loads(line)  # raises if invalid
            assert isinstance(parsed, dict)

    def test_audit_entry_contains_required_schema_fields(self, tmp_path: Path):
        """Audit entry must contain every field defined in the schema."""
        required_fields = {
            "timestamp",
            "incident_id",
            "model",
            "provider",
            "patch_file",
            "patch_hash",
            "policy_decision",
            "risk_tier",
            "review_required",
            "patch_applied",
            "tests_passed",
            "pr_url",
            "failure_reason",
            "confidence",
            "source",
        }

        log_path = tmp_path / "logs" / "sentinai-audit.jsonl"
        audit = AuditLogger(log_path=log_path)

        pipeline = _build_pipeline(tmp_path)
        pipeline._audit = audit

        incident = _make_incident()
        apply_ctx, tests_ctx = _mock_patch_run(pipeline)

        with patch.object(pipeline._engine, "suggest_fix", return_value=_make_suggestion()):
            with apply_ctx, tests_ctx:
                result = pipeline.run(incident)

        assert result.audit_entry is not None
        missing = required_fields - result.audit_entry.keys()
        assert not missing, f"Audit entry missing fields: {missing}"

    def test_audit_patch_hash_is_sha256(self, tmp_path: Path):
        """patch_hash must be a valid sha256: prefixed hex digest."""
        log_path = tmp_path / "logs" / "sentinai-audit.jsonl"
        audit = AuditLogger(log_path=log_path)

        pipeline = _build_pipeline(tmp_path)
        pipeline._audit = audit

        incident = _make_incident()
        apply_ctx, tests_ctx = _mock_patch_run(pipeline)

        with patch.object(pipeline._engine, "suggest_fix", return_value=_make_suggestion()):
            with apply_ctx, tests_ctx:
                result = pipeline.run(incident)

        patch_hash = result.audit_entry["patch_hash"]
        assert patch_hash is not None
        assert patch_hash.startswith("sha256:")
        hex_part = patch_hash[len("sha256:") :]
        assert len(hex_part) == 64
        assert all(c in "0123456789abcdef" for c in hex_part)


# ---------------------------------------------------------------------------
# C4-2 — Telemetry field accuracy
# ---------------------------------------------------------------------------


class TestTelemetryAccuracy:
    """Verify telemetry carries accurate values, not just presence."""

    def test_redactions_input_count_is_nonzero_for_dirty_incident(self, tmp_path: Path):
        """Incident with embedded secret produces redactions_input_count >= 1."""
        pipeline = _build_pipeline(tmp_path)
        dirty = _make_incident(trigger_line="ERROR AKIAIOSFODNN7EXAMPLE access denied")

        with patch.object(
            pipeline._engine,
            "suggest_fix",
            return_value=_make_suggestion(proposed_patch=None, patch_file=None),
        ):
            result = pipeline.run(dirty)

        assert result.redactions_input_count >= 1

    def test_redactions_input_count_is_zero_for_clean_incident(self, tmp_path: Path):
        """Clean incident must not produce phantom redactions."""
        pipeline = _build_pipeline(tmp_path)
        clean = _make_incident(trigger_line="ERROR connection timeout after 30s")

        with patch.object(
            pipeline._engine,
            "suggest_fix",
            return_value=_make_suggestion(proposed_patch=None, patch_file=None),
        ):
            result = pipeline.run(clean)

        assert result.redactions_input_count == 0

    def test_patch_applied_true_when_runner_succeeds(self, tmp_path: Path):
        """patch_applied must be True when apply + tests both succeed."""
        pipeline = _build_pipeline(tmp_path)
        pipeline._sandbox_available = True  # D2: override for this test
        incident = _make_incident()
        apply_ctx, tests_ctx = _mock_patch_run(pipeline)

        with patch.object(pipeline._engine, "suggest_fix", return_value=_make_suggestion()):
            with apply_ctx, tests_ctx:
                result = pipeline.run(incident)

        assert result.patch_applied is True

    def test_patch_applied_false_when_apply_fails(self, tmp_path: Path):
        """patch_applied must be False when runner.apply fails."""
        pipeline = _build_pipeline(tmp_path)
        incident = _make_incident()

        with patch.object(pipeline._engine, "suggest_fix", return_value=_make_suggestion()):
            with patch.object(
                pipeline._runner,
                "apply",
                return_value=MagicMock(success=False, error="disk full"),
            ):
                result = pipeline.run(incident)

        assert result.patch_applied is False
        assert result.failure_reason is not None
        assert "disk full" in result.failure_reason

    def test_tests_passed_false_when_tests_fail(self, tmp_path: Path):
        """tests_passed is False when pytest fails (sandbox must be available)."""
        pipeline = _build_pipeline(tmp_path)
        pipeline._sandbox_available = True  # D2: override for this test
        incident = _make_incident()

        with patch.object(pipeline._engine, "suggest_fix", return_value=_make_suggestion()):
            with patch.object(
                pipeline._runner,
                "apply",
                return_value=MagicMock(success=True, error=None),
            ):
                with patch.object(
                    pipeline._runner,
                    "run_tests",
                    return_value=MagicMock(success=False, output="1 failed", returncode=1),
                ):
                    result = pipeline.run(incident)

        assert result.tests_passed is False

    def test_confidence_rounded_in_audit(self, tmp_path: Path):
        """Confidence in audit entry must be rounded to 4 decimal places."""
        log_path = tmp_path / "logs" / "sentinai-audit.jsonl"
        audit = AuditLogger(log_path=log_path)

        pipeline = _build_pipeline(tmp_path)
        pipeline._audit = audit

        incident = _make_incident()
        suggestion = _make_suggestion(
            confidence=0.123456789,
            proposed_patch=None,
            patch_file=None,
        )

        with patch.object(pipeline._engine, "suggest_fix", return_value=suggestion):
            result = pipeline.run(incident)

        recorded_confidence = result.audit_entry["confidence"]
        assert recorded_confidence == round(0.123456789, 4)


# ---------------------------------------------------------------------------
# C4-3 — Multi-incident flow
# ---------------------------------------------------------------------------


class TestMultiIncidentFlow:
    """Sequential pipeline runs produce isolated, independent audit entries."""

    def test_three_incidents_produce_three_audit_entries(self, tmp_path: Path):
        log_path = tmp_path / "logs" / "sentinai-audit.jsonl"
        audit = AuditLogger(log_path=log_path)

        pipeline = _build_pipeline(tmp_path)
        pipeline._audit = audit

        incident_ids = ["c4-multi-001", "c4-multi-002", "c4-multi-003"]

        for iid in incident_ids:
            incident = _make_incident(incident_id=iid)
            apply_ctx, tests_ctx = _mock_patch_run(pipeline)
            with patch.object(pipeline._engine, "suggest_fix", return_value=_make_suggestion()):
                with apply_ctx, tests_ctx:
                    pipeline.run(incident)

        entries = audit.tail(n=10)
        recorded_ids = [e["incident_id"] for e in entries]
        for iid in incident_ids:
            assert iid in recorded_ids, f"Audit entry missing for {iid}"

    def test_incidents_do_not_share_audit_state(self, tmp_path: Path):
        """Each audit entry carries only its own incident_id — no bleed."""
        log_path = tmp_path / "logs" / "sentinai-audit.jsonl"
        audit = AuditLogger(log_path=log_path)

        pipeline = _build_pipeline(tmp_path)
        pipeline._audit = audit

        for i in range(3):
            incident = _make_incident(incident_id=f"isolation-{i:03d}")
            apply_ctx, tests_ctx = _mock_patch_run(pipeline)
            with patch.object(pipeline._engine, "suggest_fix", return_value=_make_suggestion()):
                with apply_ctx, tests_ctx:
                    pipeline.run(incident)

        entries = audit.tail(n=10)
        ids_seen = [e["incident_id"] for e in entries]
        # Each id must appear exactly once — no duplication or bleed
        assert len(ids_seen) == len(set(ids_seen))

    def test_concurrent_incidents_all_recorded(self, tmp_path: Path):
        """Thread-safety: concurrent runs must each produce one audit entry."""
        import threading

        log_path = tmp_path / "logs" / "sentinai-audit.jsonl"
        audit = AuditLogger(log_path=log_path)

        results: list[PipelineResult] = []
        lock = threading.Lock()

        def run_one(iid: str) -> None:
            # Each thread gets its own pipeline instance
            pipeline = _build_pipeline(tmp_path)
            pipeline._audit = audit
            incident = _make_incident(incident_id=iid)
            apply_ctx, tests_ctx = _mock_patch_run(pipeline)
            with patch.object(
                pipeline._engine,
                "suggest_fix",
                return_value=_make_suggestion(proposed_patch=None, patch_file=None),
            ):
                with apply_ctx, tests_ctx:
                    r = pipeline.run(incident)
            with lock:
                results.append(r)

        threads = [
            threading.Thread(target=run_one, args=(f"concurrent-{i:03d}",)) for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 5
        entries = audit.tail(n=20)
        recorded_ids = {e["incident_id"] for e in entries}
        for i in range(5):
            assert f"concurrent-{i:03d}" in recorded_ids


# ---------------------------------------------------------------------------
# C4-4 — Failure path — audit always written
# ---------------------------------------------------------------------------


class TestFailurePathAudit:
    """Even when pipeline fails, audit entry is always written."""

    def test_llm_failure_still_writes_audit(self, tmp_path: Path):
        log_path = tmp_path / "logs" / "sentinai-audit.jsonl"
        audit = AuditLogger(log_path=log_path)

        pipeline = _build_pipeline(tmp_path)
        pipeline._audit = audit

        incident = _make_incident()

        with patch.object(
            pipeline._engine,
            "suggest_fix",
            side_effect=RuntimeError("LLM timeout"),
        ):
            result = pipeline.run(incident)

        assert result.failure_reason is not None
        assert log_path.exists()
        entries = audit.tail(n=5)
        assert any(e["incident_id"] == incident.incident_id for e in entries)

    def test_policy_block_still_writes_audit(self, tmp_path: Path):
        """Policy BLOCK path must produce an audit entry."""

        from src.services.policy_engine import Decision, PolicyResult

        log_path = tmp_path / "logs" / "sentinai-audit.jsonl"
        audit = AuditLogger(log_path=log_path)

        pipeline = _build_pipeline(tmp_path)
        pipeline._audit = audit

        incident = _make_incident()
        blocked = PolicyResult(
            decision=Decision.BLOCK,
            reasons=("path traversal detected",),
            risk_tier="critical",
        )

        with patch.object(pipeline._engine, "suggest_fix", return_value=_make_suggestion()):
            with patch.object(pipeline._policy, "check", return_value=blocked):
                result = pipeline.run(incident)

        assert result.policy_decision == "block"
        assert result.failure_reason is not None
        entries = audit.tail(n=5)
        assert any(e["incident_id"] == incident.incident_id for e in entries)

    def test_test_failure_still_writes_audit(self, tmp_path: Path):
        """Failed pytest run must not suppress the audit entry."""
        log_path = tmp_path / "logs" / "sentinai-audit.jsonl"
        audit = AuditLogger(log_path=log_path)

        pipeline = _build_pipeline(tmp_path)
        pipeline._audit = audit
        pipeline._sandbox_available = True  # D2: override for this test

        incident = _make_incident()

        with patch.object(pipeline._engine, "suggest_fix", return_value=_make_suggestion()):
            with patch.object(
                pipeline._runner,
                "apply",
                return_value=MagicMock(success=True, error=None),
            ):
                with patch.object(
                    pipeline._runner,
                    "run_tests",
                    return_value=MagicMock(success=False, output="2 failed", returncode=1),
                ):
                    result = pipeline.run(incident)

        assert result.tests_passed is False
        entries = audit.tail(n=5)
        assert any(e["incident_id"] == incident.incident_id for e in entries)

    def test_audit_write_survives_corrupt_log_path(self, tmp_path: Path):
        """AuditLogger._append must not crash the pipeline on OSError."""
        log_path = tmp_path / "logs" / "sentinai-audit.jsonl"
        audit = AuditLogger(log_path=log_path)

        pipeline = _build_pipeline(tmp_path)
        pipeline._audit = audit

        incident = _make_incident()

        # Simulate disk-full / permission error on write
        with patch.object(audit, "_append", side_effect=OSError("disk full")):
            with patch.object(
                pipeline._engine,
                "suggest_fix",
                return_value=_make_suggestion(proposed_patch=None, patch_file=None),
            ):
                # Must not raise — pipeline is resilient to audit failures
                result = pipeline.run(incident)

        assert result.suggestion is not None
