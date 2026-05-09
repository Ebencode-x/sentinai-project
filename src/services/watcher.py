"""Core real-time log watcher for SentinAI.

This module contains the heart of the "self-healing" detection pipeline:
it tails a local log file, looks for crash-related signals, and aggregates
multiline stack traces into a single incident object that can be sent to an LLM.
"""

from __future__ import annotations

import hashlib
import re
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Deque, Iterable, Iterator, Optional

from src.models.events import LogIncident


@dataclass
class WatcherConfig:
    """Runtime settings for log tailing and incident detection."""

    log_file_path: str
    poll_interval_seconds: float = 0.5
    context_lines_before_error: int = 10
    max_stacktrace_lines: int = 40


class LogWatcher:
    """Watch a local log file and emit structured incidents.

    Design notes:
    - We keep this class synchronous to stay easy to test and reason about.
    - The tailing strategy is "poll + seek", which works cross-platform and
      is enough for local demo scenarios.
    - Stack traces are aggregated using simple heuristics so the incident sent
      to AI has enough context for useful remediation suggestions.
    """

    ERROR_PATTERNS = (
        re.compile(r"\bERROR\b", re.IGNORECASE),
        re.compile(r"\bEXCEPTION\b", re.IGNORECASE),
        re.compile(r"\bTraceback\b", re.IGNORECASE),
        re.compile(r"\b500\b"),
    )

    STACKTRACE_CONTINUATION_PATTERNS = (
        re.compile(r"^\s+File\s+\".*\", line \d+"),  # Python traceback frames
        re.compile(r"^\s+[A-Za-z_][A-Za-z0-9_]*Error:"),  # Indented error summary lines
        re.compile(
            r"^[A-Za-z_][A-Za-z0-9_]*Error:.*"
        ),  # Column-0 Python errors (common in logs)
        re.compile(r"^\s+at\s+"),  # Typical JS/TS stack trace lines
        re.compile(r"^\s+\.\.\."),  # Continuation marker
    )

    def __init__(self, config: WatcherConfig) -> None:
        self.config = config
        self._log_path = Path(config.log_file_path)
        self._context_buffer: Deque[str] = deque(
            maxlen=config.context_lines_before_error
        )
        self._file_position: int = 0

    def initialize_position(self, start_from_end: bool = True) -> None:
        """Set initial file cursor.

        Args:
            start_from_end: If True, begin tailing from current EOF (ignore old logs).
                            If False, start from beginning and process all existing lines.
        """
        self._ensure_log_file_exists()
        self._file_position = self._log_path.stat().st_size if start_from_end else 0

    def read_new_lines(self) -> list[str]:
        """Read lines appended since the last read.

        Returns:
            A list of newly appended lines (without trailing newline).
        """
        self._ensure_log_file_exists()

        with self._log_path.open("r", encoding="utf-8", errors="replace") as file:
            file.seek(self._file_position)
            lines = [line.rstrip("\n") for line in file.readlines()]
            self._file_position = file.tell()

        return lines

    def scan_once(self) -> list[LogIncident]:
        """Run a single scan pass and return any newly detected incidents."""
        new_lines = self.read_new_lines()
        incidents: list[LogIncident] = []

        line_iterator = iter(range(len(new_lines)))
        for index in line_iterator:
            line = new_lines[index]
            self._context_buffer.append(line)

            if not self._is_error_signal(line):
                continue

            # Collect stack-trace style lines that follow the trigger line.
            multiline_block, consumed = self._collect_multiline_error_block(
                trigger_line_index=index,
                lines=new_lines,
            )

            # Skip indexes already consumed by multiline aggregation.
            for _ in range(consumed):
                next(line_iterator, None)

            incident = self._build_incident(multiline_block)
            incidents.append(incident)

        return incidents

    def follow(
        self, stop_after_iterations: Optional[int] = None
    ) -> Iterator[LogIncident]:
        """Continuously tail logs and yield incidents as they appear.

        Args:
            stop_after_iterations: Test helper to stop after N polling loops.
                                   Use None for infinite streaming.
        """
        self.initialize_position(start_from_end=True)
        iterations = 0

        while True:
            for incident in self.scan_once():
                yield incident

            iterations += 1
            if (
                stop_after_iterations is not None
                and iterations >= stop_after_iterations
            ):
                break

            time.sleep(self.config.poll_interval_seconds)

    def _collect_multiline_error_block(
        self, trigger_line_index: int, lines: list[str]
    ) -> tuple[list[str], int]:
        """Aggregate trigger + continuation lines into one incident block.

        Returns:
            Tuple of:
            - collected lines,
            - number of extra lines consumed after the trigger line.
        """
        collected = [lines[trigger_line_index]]
        consumed = 0

        for next_index in range(trigger_line_index + 1, len(lines)):
            candidate = lines[next_index]

            if len(collected) >= self.config.max_stacktrace_lines:
                break

            # Continue while it still looks like stack trace detail.
            if self._looks_like_stacktrace_continuation(candidate):
                collected.append(candidate)
                consumed += 1
                continue

            # A blank line may appear inside traces; keep one soft boundary.
            if candidate.strip() == "":
                collected.append(candidate)
                consumed += 1
                continue

            break

        return collected, consumed

    def _build_incident(self, error_block: Iterable[str]) -> LogIncident:
        """Create a structured incident object from error lines + context."""
        block_lines = list(error_block)
        context_lines = list(self._context_buffer)
        merged_text = "\n".join(block_lines)
        fingerprint = self._fingerprint(merged_text)

        return LogIncident(
            incident_id=fingerprint,
            detected_at_utc=datetime.now(timezone.utc),
            severity="critical",
            trigger_line=block_lines[0] if block_lines else "",
            stacktrace=merged_text,
            context_before_error="\n".join(
                context_lines[: -len(block_lines)]
                if len(context_lines) > len(block_lines)
                else context_lines
            ),
        )

    def _is_error_signal(self, line: str) -> bool:
        """Return True when a line matches one of our crash/error indicators."""
        return any(pattern.search(line) for pattern in self.ERROR_PATTERNS)

    def _looks_like_stacktrace_continuation(self, line: str) -> bool:
        """Heuristic to decide whether line belongs to the same stacktrace."""
        return any(
            pattern.search(line) for pattern in self.STACKTRACE_CONTINUATION_PATTERNS
        )

    @staticmethod
    def _fingerprint(text: str) -> str:
        """Deterministic short hash used for deduping similar incidents."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def _ensure_log_file_exists(self) -> None:
        """Create parent directory and log file when missing."""
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._log_path.exists():
            self._log_path.touch()
