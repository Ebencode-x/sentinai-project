"""Shared in-memory state for the demo API."""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.core.config import settings
from src.core.metrics import metrics
from src.integrations.notifier import notify
from src.models.events import LogIncident, RemediationSuggestion
from src.services.remediation_engine import RemediationEngine
from src.services.watcher import LogWatcher, WatcherConfig

logger = logging.getLogger(__name__)


@dataclass
class AppState:
    """Mutable runtime state used by routes and startup hooks."""

    watcher: LogWatcher = field(
        default_factory=lambda: LogWatcher(
            WatcherConfig(log_file_path=settings.log_file_path),
        )
    )
    remediation_engine: RemediationEngine = field(default_factory=RemediationEngine)
    recent_incidents: deque[LogIncident] = field(
        default_factory=lambda: deque(maxlen=settings.max_recent_incidents)
    )
    recent_suggestions: deque[RemediationSuggestion] = field(
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
            self._save_incidents()
            suggestion = self.remediation_engine.suggest_fix(incident)
            self.recent_suggestions.append(suggestion)

            # Milestone 3: fire Slack + webhook notifications
            notify(incident, suggestion)

            added += 1

        self.total_scan_runs += 1
        self.last_scan_at_utc = datetime.now(UTC)
        self.last_scan_new_incidents = added
        return added

    def stats_snapshot(self) -> dict:
        """Lightweight runtime metrics for demos and observability export.

        Acquires _scan_lock to ensure a consistent view of shared state
        while scan_logs_once() may be running concurrently.
        """
        with self._scan_lock:
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

    def _incidents_cache_path(self):
        import pathlib

        p = pathlib.Path(self.watcher.config.log_file_path).parent / "incidents.json"
        return p

    def _save_incidents(self):
        import json

        try:
            data = [inc.model_dump(mode="json") for inc in self.recent_incidents]
            self._incidents_cache_path().write_text(json.dumps(data, default=str))
        except Exception as e:
            logger.warning("[state] Failed to save incidents: %s", e)

    def load_incidents(self):
        import json

        from src.models.events import LogIncident

        p = self._incidents_cache_path()
        if not p.exists():
            return
        try:
            data = json.loads(p.read_text())
            for d in data:
                try:
                    inc = LogIncident(**d)
                    if inc.incident_id not in self._incident_dedupe:
                        self._incident_dedupe[inc.incident_id] = None
                        self.recent_incidents.append(inc)
                except Exception:
                    pass
            logger.info("[state] Loaded %d incidents from cache", len(self.recent_incidents))
        except Exception as e:
            logger.warning("[state] Failed to load incidents: %s", e)


app_state = AppState()
