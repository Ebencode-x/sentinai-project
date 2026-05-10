"""Shared in-memory state for the demo API."""

from __future__ import annotations

import threading
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Deque

from src.core.config import settings
from src.core.metrics import metrics
from src.integrations.notifier import notify
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
    _scan_lock: threading.Lock = field(default_factory=threading.Lock)
    total_scan_runs: int = 0
    last_scan_at_utc: datetime | None = None
    last_scan_new_incidents: int = 0

    def scan_logs_once(self) -> int:
        with self._scan_lock:
            return self._do_scan()

    def _do_scan(self) -> int:
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
            suggestion = self.remediation_engine.suggest_fix(incident)
            self.recent_suggestions.append(suggestion)

            # Milestone 3: fire Slack + webhook notifications
            notify(incident, suggestion)

            added += 1

        self.total_scan_runs += 1
        self.last_scan_at_utc = datetime.now(timezone.utc)
        self.last_scan_new_incidents = added
        return added

    def stats_snapshot(self) -> dict:
        """Lightweight runtime metrics for demos and observability export."""
        by_source: dict[str, int] = {"stub": 0, "provider": 0, "fallback": 0}
        for suggestion in self.recent_suggestions:
            key = suggestion.source
            if key in by_source:
                by_source[key] += 1

        return {
            "service": "sentinai",
            "log_file_path": settings.log_file_path,
            "llm_provider": settings.llm_provider,
            "buffer_incident_count": len(self.recent_incidents),
            "buffer_suggestion_count": len(self.recent_suggestions),
            "dedupe_fingerprints_tracked": len(self._incident_dedupe),
            "dedupe_window_max": settings.incident_dedupe_window,
            "total_scan_runs": self.total_scan_runs,
            "last_scan_at_utc": self.last_scan_at_utc.isoformat()
            if self.last_scan_at_utc
            else None,
            "last_scan_new_incidents": self.last_scan_new_incidents,
            "recent_suggestions_by_source": by_source,
            "llm_metrics": metrics.snapshot(),
        }


app_state = AppState()
