"""M8 tests for src/services/watcher.py."""
from __future__ import annotations

import hashlib
from pathlib import Path  # noqa: F401
from unittest.mock import patch

import pytest

from src.models.events import LogIncident
from src.services.watcher import LogWatcher, WatcherConfig


@pytest.fixture
def tmp_log(tmp_path):
    p = tmp_path / "app.log"
    p.touch()
    return p


@pytest.fixture
def watcher(tmp_log):
    cfg = WatcherConfig(log_file_path=str(tmp_log))
    w = LogWatcher(cfg)
    w.initialize_position(start_from_end=False)
    return w


class TestWatcherConfig:
    def test_defaults(self):
        cfg = WatcherConfig(log_file_path="logs/app.log")
        assert cfg.poll_interval_seconds == 0.5
        assert cfg.context_lines_before_error == 10
        assert cfg.max_stacktrace_lines == 40

    def test_custom_values(self):
        cfg = WatcherConfig(log_file_path="x.log", poll_interval_seconds=1.0, max_stacktrace_lines=20)
        assert cfg.poll_interval_seconds == 1.0
        assert cfg.max_stacktrace_lines == 20


class TestInitializePosition:
    def test_start_from_end_sets_file_size(self, tmp_log):
        tmp_log.write_text("hello\nworld\n")
        cfg = WatcherConfig(log_file_path=str(tmp_log))
        w = LogWatcher(cfg)
        w.initialize_position(start_from_end=True)
        assert w._file_position == tmp_log.stat().st_size

    def test_start_from_beginning(self, tmp_log):
        tmp_log.write_text("some content")
        cfg = WatcherConfig(log_file_path=str(tmp_log))
        w = LogWatcher(cfg)
        w.initialize_position(start_from_end=False)
        assert w._file_position == 0

    def test_creates_missing_log_file(self, tmp_path):
        missing = tmp_path / "sub" / "new.log"
        cfg = WatcherConfig(log_file_path=str(missing))
        w = LogWatcher(cfg)
        w.initialize_position(start_from_end=False)
        assert missing.exists()


class TestReadNewLines:
    def test_empty_file_returns_empty_list(self, watcher, tmp_log):
        assert watcher.read_new_lines() == []

    def test_reads_lines_written_after_position(self, watcher, tmp_log):
        tmp_log.write_text("line one\nline two\n")
        watcher._file_position = 0
        lines = watcher.read_new_lines()
        assert lines == ["line one", "line two"]

    def test_incremental_reads(self, watcher, tmp_log):
        tmp_log.write_text("first\n")
        lines1 = watcher.read_new_lines()
        assert lines1 == ["first"]
        with tmp_log.open("a") as f:
            f.write("second\n")
        lines2 = watcher.read_new_lines()
        assert lines2 == ["second"]

    def test_strips_trailing_newline(self, watcher, tmp_log):
        tmp_log.write_text("hello\n")
        watcher._file_position = 0
        lines = watcher.read_new_lines()
        assert lines == ["hello"]

    def test_creates_missing_file_on_read(self, tmp_path):
        missing = tmp_path / "ghost.log"
        cfg = WatcherConfig(log_file_path=str(missing))
        w = LogWatcher(cfg)
        result = w.read_new_lines()
        assert result == []
        assert missing.exists()


class TestIsErrorSignal:
    @pytest.mark.parametrize("line", [
        "2024-01-01 ERROR something broke",
        "Unhandled EXCEPTION in handler",
        "Traceback (most recent call last):",
        "Request returned 500",
        "error in lower case",
    ])
    def test_detects_error_lines(self, watcher, line):
        assert watcher._is_error_signal(line) is True

    @pytest.mark.parametrize("line", [
        "INFO server started on port 8000",
        "DEBUG fetching config",
        "GET /health 200",
    ])
    def test_ignores_clean_lines(self, watcher, line):
        assert watcher._is_error_signal(line) is False


class TestStacktraceContinuation:
    @pytest.mark.parametrize("line", [
        '  File "app.py", line 42',
        "  ValueError: bad value",
        "ValueError: something went wrong",
        "  at Object.render (index.js:10)",
        "  ...",
    ])
    def test_recognises_continuation_lines(self, watcher, line):
        assert watcher._looks_like_stacktrace_continuation(line) is True

    @pytest.mark.parametrize("line", [
        "INFO request completed",
        "2024-01-01 DEBUG all good",
    ])
    def test_rejects_non_continuation(self, watcher, line):
        assert watcher._looks_like_stacktrace_continuation(line) is False


class TestFingerprint:
    def test_deterministic(self):
        assert LogWatcher._fingerprint("same") == LogWatcher._fingerprint("same")

    def test_different_text_different_hash(self):
        assert LogWatcher._fingerprint("a") != LogWatcher._fingerprint("b")

    def test_length_is_16(self):
        assert len(LogWatcher._fingerprint("anything")) == 16

    def test_matches_sha256(self):
        text = "test incident"
        expected = hashlib.sha256(text.encode()).hexdigest()[:16]
        assert LogWatcher._fingerprint(text) == expected


class TestBuildIncident:
    def test_returns_log_incident(self, watcher):
        incident = watcher._build_incident(["ERROR something failed"])
        assert isinstance(incident, LogIncident)

    def test_trigger_line_is_first_line(self, watcher):
        incident = watcher._build_incident(["ERROR line one", "  File app.py line 5"])
        assert incident.trigger_line == "ERROR line one"

    def test_stacktrace_joins_all_lines(self, watcher):
        lines = ["ERROR boom", "  File x.py, line 1", "  ValueError: bad"]
        incident = watcher._build_incident(lines)
        assert "ERROR boom" in incident.stacktrace
        assert "ValueError: bad" in incident.stacktrace

    def test_severity_is_critical(self, watcher):
        incident = watcher._build_incident(["ERROR crash"])
        assert incident.severity == "critical"

    def test_empty_block_gives_empty_trigger(self, watcher):
        incident = watcher._build_incident([])
        assert incident.trigger_line == ""

    def test_incident_id_is_fingerprint(self, watcher):
        lines = ["ERROR test"]
        incident = watcher._build_incident(lines)
        expected_id = LogWatcher._fingerprint("\n".join(lines))
        assert incident.incident_id == expected_id


class TestCollectMultilineBlock:
    def test_collects_continuation_lines(self, watcher):
        lines = [
            "ERROR handler crashed",
            '  File "app.py", line 10',
            "  ValueError: bad input",
            "INFO next request",
        ]
        collected, consumed = watcher._collect_multiline_error_block(0, lines)
        assert consumed == 2
        assert len(collected) == 3

    def test_stops_at_non_continuation(self, watcher):
        lines = ["ERROR crash", "INFO clean line"]
        collected, consumed = watcher._collect_multiline_error_block(0, lines)
        assert consumed == 0
        assert collected == ["ERROR crash"]

    def test_blank_line_is_included(self, watcher):
        lines = ["ERROR crash", "", '  File "x.py", line 1']
        collected, consumed = watcher._collect_multiline_error_block(0, lines)
        assert consumed == 2
        assert "" in collected

    def test_respects_max_stacktrace_lines(self, tmp_log):
        cfg = WatcherConfig(log_file_path=str(tmp_log), max_stacktrace_lines=3)
        w = LogWatcher(cfg)
        lines = ["ERROR x"] + ['  File "f.py", line 1'] * 10
        collected, consumed = w._collect_multiline_error_block(0, lines)
        assert len(collected) <= 3

    def test_single_line_no_continuation(self, watcher):
        lines = ["ERROR alone"]
        collected, consumed = watcher._collect_multiline_error_block(0, lines)
        assert collected == ["ERROR alone"]
        assert consumed == 0


class TestScanOnce:
    def test_no_errors_returns_empty(self, watcher, tmp_log):
        tmp_log.write_text("INFO all good\nDEBUG nothing here\n")
        watcher._file_position = 0
        assert watcher.scan_once() == []

    def test_detects_single_error(self, watcher, tmp_log):
        tmp_log.write_text("ERROR database connection failed\n")
        watcher._file_position = 0
        incidents = watcher.scan_once()
        assert len(incidents) == 1
        assert "database connection failed" in incidents[0].trigger_line

    def test_detects_multiple_errors(self, watcher, tmp_log):
        tmp_log.write_text("ERROR first\nINFO ok\nERROR second\n")
        watcher._file_position = 0
        assert len(watcher.scan_once()) == 2

    def test_aggregates_multiline_traceback(self, watcher, tmp_log):
        content = "Traceback (most recent call last):\n  File \"app.py\", line 10\n  ValueError: bad\nINFO next\n"
        tmp_log.write_text(content)
        watcher._file_position = 0
        incidents = watcher.scan_once()
        assert len(incidents) == 1
        assert "ValueError" in incidents[0].stacktrace

    def test_returns_log_incident_objects(self, watcher, tmp_log):
        tmp_log.write_text("ERROR crash!\n")
        watcher._file_position = 0
        incidents = watcher.scan_once()
        assert all(isinstance(i, LogIncident) for i in incidents)

    def test_500_signal_detected(self, watcher, tmp_log):
        tmp_log.write_text("GET /api/data 500 Internal Server Error\n")
        watcher._file_position = 0
        assert len(watcher.scan_once()) == 1

    def test_incremental_scan_only_reads_new_lines(self, watcher, tmp_log):
        tmp_log.write_text("INFO warm up\n")
        watcher.read_new_lines()
        with tmp_log.open("a") as f:
            f.write("ERROR new error\n")
        assert len(watcher.scan_once()) == 1


class TestFollow:
    def test_follow_stops_after_n_iterations(self, tmp_log):
        cfg = WatcherConfig(log_file_path=str(tmp_log), poll_interval_seconds=0)
        w = LogWatcher(cfg)
        with patch("time.sleep"):
            result = list(w.follow(stop_after_iterations=2))
        assert isinstance(result, list)

    def test_follow_yields_incidents_from_log(self, tmp_log):
        tmp_log.write_text("ERROR boom\n")
        cfg = WatcherConfig(log_file_path=str(tmp_log), poll_interval_seconds=0)
        w = LogWatcher(cfg)
        w._file_position = 0
        with patch.object(w, "initialize_position"):
            with patch("time.sleep"):
                result = list(w.follow(stop_after_iterations=1))
        assert len(result) >= 1


class TestEnsureLogFileExists:
    def test_creates_nested_directories_and_file(self, tmp_path):
        nested = tmp_path / "a" / "b" / "app.log"
        cfg = WatcherConfig(log_file_path=str(nested))
        w = LogWatcher(cfg)
        w._ensure_log_file_exists()
        assert nested.exists()

    def test_no_error_if_file_already_exists(self, tmp_log):
        cfg = WatcherConfig(log_file_path=str(tmp_log))
        w = LogWatcher(cfg)
        w._ensure_log_file_exists()
        assert tmp_log.exists()
