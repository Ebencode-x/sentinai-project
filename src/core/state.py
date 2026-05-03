"""Shared in-memory state for the demo API."""

from __future__ import annotations

from collections import OrderedDict, deque
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
    _incident_dedupe: OrderedDict[str, None] = field(default_factory=OrderedDict)

    def scan_logs_once(self) -> int:
        incidents = self.watcher.scan_once()
        added = 0
        for incident in incidents:
            if incident.incident_id in self._incident_dedupe:
                continue
            self._incident_dedupe[incident.incident_id] = None
            max_window = max(1, settings.incident_dedupe_window)
            while len(self._incident_dedupe) > max_window:
                self._incident_dedupe.popitem(last=False)

            self.recent_incidents.append(incident)
            self.recent_suggestions.append(self.remediation_engine.suggest_fix(incident))
            added += 1
        return added


app_state = AppState()

