"""Basic tests for watcher error detection behavior."""

from __future__ import annotations

from pathlib import Path

from src.services.watcher import LogWatcher, WatcherConfig


def test_scan_once_detects_error_and_collects_traceback(tmp_path: Path) -> None:
    log_file = tmp_path / "app.log"
    log_file.write_text(
        "\n".join(
            [
                "INFO booting app",
                "ERROR request failed",
                "  File \"main.py\", line 12, in handler",
                "ValueError: bad value",
            ]
        ),
        encoding="utf-8",
    )

    watcher = LogWatcher(WatcherConfig(log_file_path=str(log_file), poll_interval_seconds=0.0))
    watcher.initialize_position(start_from_end=False)
    incidents = watcher.scan_once()

    assert len(incidents) == 1
    assert "ERROR request failed" in incidents[0].stacktrace
    assert "ValueError: bad value" in incidents[0].stacktrace

