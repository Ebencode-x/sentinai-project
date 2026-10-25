"""Regression tests: real Python tracebacks, log truncation, stable fingerprints."""

import traceback
from pathlib import Path

from src.services.watcher import LogWatcher, WatcherConfig


def _watcher(tmp_path: Path) -> tuple[LogWatcher, Path]:
    log = tmp_path / "app.log"
    watcher = LogWatcher(WatcherConfig(log_file_path=str(log)))
    watcher.initialize_position(start_from_end=True)
    return watcher, log


def _boom() -> None:
    raise KeyError("missing")


def _real_traceback() -> str:
    try:
        _boom()
    except KeyError:
        return traceback.format_exc()
    raise AssertionError("unreachable")


def test_python_traceback_is_one_incident(tmp_path: Path) -> None:
    watcher, log = _watcher(tmp_path)
    log.write_text(
        "INFO ok\nERROR [agrolink] boom\n" + _real_traceback() + "INFO next\n",
        encoding="utf-8",
    )
    incidents = watcher.scan_once()
    assert len(incidents) == 1
    block = incidents[0].stacktrace
    assert "ERROR [agrolink] boom" in block
    assert "Traceback (most recent call last):" in block
    assert 'raise KeyError("missing")' in block
    assert "KeyError: 'missing'" in block
    assert "INFO next" not in block


def test_chained_exception_stays_in_one_incident(tmp_path: Path) -> None:
    watcher, log = _watcher(tmp_path)
    try:
        try:
            _boom()
        except KeyError as exc:
            raise RuntimeError("wrapped") from exc
    except RuntimeError:
        chained = traceback.format_exc()
    log.write_text("ERROR [agrolink] chained\n" + chained + "INFO next\n", encoding="utf-8")
    incidents = watcher.scan_once()
    assert len(incidents) == 1
    block = incidents[0].stacktrace
    assert "The above exception was the direct cause" in block
    assert "RuntimeError: wrapped" in block


def test_cursor_resets_after_truncation(tmp_path: Path) -> None:
    watcher, log = _watcher(tmp_path)
    log.write_text("INFO a\n" * 50, encoding="utf-8")
    assert watcher.scan_once() == []
    log.write_text("ERROR [agrolink] after truncate\n", encoding="utf-8")
    assert len(watcher.scan_once()) == 1


def test_fingerprint_ignores_volatile_numbers() -> None:
    frame = '\n  File "app.py", line {n}, in view'
    a = LogWatcher._fingerprint("ERROR listing 123 failed" + frame.format(n=10))
    b = LogWatcher._fingerprint("ERROR listing 98765 failed" + frame.format(n=12))
    c = LogWatcher._fingerprint("ERROR payment 123 failed" + frame.format(n=10))
    assert a == b
    assert a != c
