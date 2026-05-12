"""Tests for AuditLogger — A4."""

from __future__ import annotations

from pathlib import Path

from src.core.audit import AuditLogger


def _logger(tmp_path: Path) -> AuditLogger:
    return AuditLogger(log_path=tmp_path / "audit.jsonl")


def _entry(**kwargs) -> dict:
    base = dict(
        incident_id="inc-001",
        model="claude-sonnet-4",
        provider="anthropic",
        patch_file="src/x.py",
        patch="-old\n+new\n",
        policy_decision="allow",
        risk_tier="low",
        review_required=False,
        patch_applied=True,
        tests_passed=True,
        pr_url="https://github.com/pr/1",
        failure_reason=None,
        confidence=0.82,
        source="provider",
    )
    base.update(kwargs)
    return base


class TestAuditLogger:
    def test_record_creates_file(self, tmp_path: Path) -> None:
        al = _logger(tmp_path)
        al.record(**_entry())
        assert (tmp_path / "audit.jsonl").exists()

    def test_record_returns_dict(self, tmp_path: Path) -> None:
        al = _logger(tmp_path)
        result = al.record(**_entry())
        assert isinstance(result, dict)
        assert result["incident_id"] == "inc-001"

    def test_record_has_timestamp(self, tmp_path: Path) -> None:
        al = _logger(tmp_path)
        entry = al.record(**_entry())
        assert "timestamp" in entry
        assert "T" in entry["timestamp"]

    def test_patch_hash_computed(self, tmp_path: Path) -> None:
        al = _logger(tmp_path)
        entry = al.record(**_entry(patch="-old\n+new\n"))
        assert entry["patch_hash"].startswith("sha256:")

    def test_no_patch_hash_is_none(self, tmp_path: Path) -> None:
        al = _logger(tmp_path)
        entry = al.record(**_entry(patch=None))
        assert entry["patch_hash"] is None

    def test_tail_returns_entries(self, tmp_path: Path) -> None:
        al = _logger(tmp_path)
        al.record(**_entry(incident_id="a"))
        al.record(**_entry(incident_id="b"))
        entries = al.tail(n=10)
        assert len(entries) == 2
        assert entries[0]["incident_id"] == "a"
        assert entries[1]["incident_id"] == "b"

    def test_tail_respects_limit(self, tmp_path: Path) -> None:
        al = _logger(tmp_path)
        for i in range(10):
            al.record(**_entry(incident_id=f"inc-{i}"))
        assert len(al.tail(n=3)) == 3

    def test_find_by_incident_id(self, tmp_path: Path) -> None:
        al = _logger(tmp_path)
        al.record(**_entry(incident_id="target"))
        al.record(**_entry(incident_id="other"))
        results = al.find("target")
        assert len(results) == 1
        assert results[0]["incident_id"] == "target"

    def test_tail_empty_when_no_file(self, tmp_path: Path) -> None:
        al = _logger(tmp_path)
        assert al.tail() == []

    def test_multiple_records_appended(self, tmp_path: Path) -> None:
        al = _logger(tmp_path)
        for i in range(5):
            al.record(**_entry(incident_id=f"inc-{i}"))
        lines = (tmp_path / "audit.jsonl").read_text().splitlines()
        assert len(lines) == 5

    def test_confidence_rounded(self, tmp_path: Path) -> None:
        al = _logger(tmp_path)
        entry = al.record(**_entry(confidence=0.123456789))
        assert entry["confidence"] == 0.1235

    def test_audit_entry_on_pipeline_result(self, tmp_path: Path) -> None:
        """audit_entry is attached to PipelineResult after run()."""
        from datetime import UTC, datetime
        from unittest.mock import MagicMock, patch

        import yaml

        from src.models.events import LogIncident, RemediationSuggestion
        from src.services.pipeline import RemediationPipeline

        policy = {
            "allowed_paths": ["src/", "tests/"],
            "blocked_paths": [],
            "max_files_changed": 5,
            "max_patch_lines": 120,
            "forbidden_patterns": [],
            "risk_tiers": {
                "low": {"auto_pr": True, "patterns": ["tests/"]},
            },
        }
        pf = tmp_path / "policy.yml"
        pf.write_text(yaml.dump(policy), encoding="utf-8")

        incident = LogIncident(
            incident_id="audit-test",
            detected_at_utc=datetime.now(UTC),
            severity="critical",
            trigger_line="err",
            stacktrace="tb",
            context_before_error="",
        )
        sug = RemediationSuggestion(
            summary="fix",
            proposed_code_fix="fix",
            proposed_config_change="none",
            confidence=0.7,
            risks="low",
            source="stub",
        )
        with (
            patch("src.services.pipeline.GitHubClient"),
            patch("src.services.pipeline.build_llm_client"),
        ):
            pipeline = RemediationPipeline(
                project_root=tmp_path,
                dry_run=True,
                policy_path=pf,
            )
        pipeline._engine = MagicMock()
        pipeline._engine.suggest_fix.return_value = sug
        pipeline._audit = AuditLogger(log_path=tmp_path / "audit.jsonl")

        result = pipeline.run(incident)
        assert result.audit_entry is not None
        assert result.audit_entry["incident_id"] == "audit-test"
