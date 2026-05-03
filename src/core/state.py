"""Shared in-memory state for the demo API."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque

from src.core.config import settings
from src.models.events import LogIncident, RemediationSuggestion
from src.services.remediation_engine import RemediationEngine
from src.services.watcher import LogWatcher, WatcherConfig


@dataclass
class AppState:
    """Mutable runtime state used by routes and startup hooks."""

    watcher: LogWatcher = field(
        default_factory=lambda: LogWatcher(
            WatcherConfig(log_file_path=settings.log_file_path),
        )
    )
    remediation_engine: RemediationEngine = field(default_factory=RemediationEngine)
    recent_incidents: Deque[LogIncident] = field(
        default_factory=lambda: deque(maxlen=settings.max_recent_incidents)
    )
    recent_suggestions: Deque[RemediationSuggestion] = field(
        default_factory=lambda: deque(maxlen=settings.max_recent_incidents)
    )

    def scan_logs_once(self) -> int:
        incidents = self.watcher.scan_once()
        for incident in incidents:
            self.recent_incidents.append(incident)
            self.recent_suggestions.append(self.remediation_engine.suggest_fix(incident))
        return len(incidents)


app_state = AppState()

