"""Tests for src/cli.py — SentinAI CLI."""

from __future__ import annotations

from typer.testing import CliRunner

from src.cli import app

runner = CliRunner()


class TestVersionCommand:
    def test_version_exits_zero(self):
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0

    def test_version_output_contains_sentinai(self):
        result = runner.invoke(app, ["version"])
        assert "sentinai" in result.output


class TestScanCommand:
    def test_scan_valid_file_exits_zero(self, tmp_path):
        log = tmp_path / "app.log"
        log.write_text("INFO all good\nINFO startup complete\n", encoding="utf-8")
        result = runner.invoke(app, ["scan", str(log)])
        assert result.exit_code == 0

    def test_scan_detects_error_lines(self, tmp_path):
        log = tmp_path / "app.log"
        log.write_text("ERROR something broke\nINFO ok\n", encoding="utf-8")
        result = runner.invoke(app, ["scan", str(log), "--verbose"])
        assert "Incidents found: 1" in result.output

    def test_scan_no_incidents(self, tmp_path):
        log = tmp_path / "app.log"
        log.write_text("INFO startup\nINFO all good\n", encoding="utf-8")
        result = runner.invoke(app, ["scan", str(log)])
        assert "No incidents detected" in result.output

    def test_scan_tail_limits_lines(self, tmp_path):
        log = tmp_path / "app.log"
        lines = "INFO line\n" * 200
        log.write_text(lines, encoding="utf-8")
        result = runner.invoke(app, ["scan", str(log), "--tail", "10"])
        assert "Lines loaded: 10" in result.output

    def test_scan_detects_critical(self, tmp_path):
        log = tmp_path / "app.log"
        log.write_text("CRITICAL disk full\n", encoding="utf-8")
        result = runner.invoke(app, ["scan", str(log), "--verbose"])
        assert "Incidents found: 1" in result.output

    def test_scan_detects_traceback(self, tmp_path):
        log = tmp_path / "app.log"
        log.write_text("Traceback (most recent call last):\n", encoding="utf-8")
        result = runner.invoke(app, ["scan", str(log), "--verbose"])
        assert "Incidents found: 1" in result.output

    def test_scan_verbose_shows_incident_lines(self, tmp_path):
        log = tmp_path / "app.log"
        log.write_text("ERROR db connection failed\n", encoding="utf-8")
        result = runner.invoke(app, ["scan", str(log), "--verbose"])
        assert "db connection failed" in result.output

    def test_scan_nonexistent_file_fails(self):
        result = runner.invoke(app, ["scan", "nonexistent.log"])
        assert result.exit_code != 0

    def test_scan_output_shows_filename(self, tmp_path):
        log = tmp_path / "app.log"
        log.write_text("INFO ok\n", encoding="utf-8")
        result = runner.invoke(app, ["scan", str(log)])
        assert "app.log" in result.output
