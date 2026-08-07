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
    autonomy_mode: str = field(default_factory=lambda: settings.autonomy_mode)
    notification_channels: list[dict] = field(default_factory=list)
    rollback_ledger: list[dict] = field(default_factory=list)
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
            suggestion = self.remediation_engine.suggest_fix(
                incident, autonomy_mode=self.autonomy_mode
            )
            self.recent_suggestions.append(suggestion)

            if suggestion.pr_number and suggestion.patch_file and suggestion.before_sha:
                self.add_rollback_ledger_entry(
                    incident_id=incident.incident_id,
                    pr_number=suggestion.pr_number,
                    pr_url=suggestion.pr_url,
                    branch_name=suggestion.branch_name,
                    patch_file=suggestion.patch_file,
                    before_sha=suggestion.before_sha,
                )

            # Milestone 3: fire Slack + webhook notifications
            notify(incident, suggestion, channels=self.notification_channels)

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

    def _settings_cache_path(self):
        import pathlib

        p = pathlib.Path(self.watcher.config.log_file_path).parent / "settings.json"
        return p

    def _save_settings(self):
        import json

        try:
            self._settings_cache_path().write_text(
                json.dumps(
                    {
                        "autonomy_mode": self.autonomy_mode,
                        "notification_channels": self.notification_channels,
                    }
                )
            )
        except Exception as e:
            logger.warning("[state] Failed to save settings: %s", e)

    def load_settings(self):
        import json

        p = self._settings_cache_path()
        if not p.exists():
            return
        try:
            data = json.loads(p.read_text())
            mode = data.get("autonomy_mode")
            if mode in ("propose_only", "auto_pr"):
                self.autonomy_mode = mode
                logger.info("[state] Loaded autonomy_mode=%s from cache", mode)
            channels = data.get("notification_channels")
            if isinstance(channels, list):
                self.notification_channels = channels
                logger.info("[state] Loaded %d notification channel(s) from cache", len(channels))
        except Exception as e:
            logger.warning("[state] Failed to load settings: %s", e)

    def _rollback_ledger_cache_path(self):
        import pathlib

        p = pathlib.Path(self.watcher.config.log_file_path).parent / "rollback_ledger.json"
        return p

    def _save_rollback_ledger(self):
        import json

        try:
            self._rollback_ledger_cache_path().write_text(
                json.dumps(self.rollback_ledger, default=str)
            )
        except Exception as e:
            logger.warning("[state] Failed to save rollback ledger: %s", e)

    def load_rollback_ledger(self):
        import json

        p = self._rollback_ledger_cache_path()
        if not p.exists():
            return
        try:
            data = json.loads(p.read_text())
            if isinstance(data, list):
                self.rollback_ledger = data
                logger.info("[state] Loaded %d rollback ledger entr(y/ies) from cache", len(data))
        except Exception as e:
            logger.warning("[state] Failed to load rollback ledger: %s", e)

    def add_rollback_ledger_entry(
        self,
        incident_id: str,
        pr_number: int,
        pr_url: str | None,
        branch_name: str | None,
        patch_file: str,
        before_sha: str,
    ) -> dict:
        import uuid
        from datetime import UTC, datetime

        entry = {
            "id": str(uuid.uuid4()),
            "incident_id": incident_id,
            "pr_number": pr_number,
            "pr_url": pr_url,
            "branch_name": branch_name,
            "patch_file": patch_file,
            "before_sha": before_sha,
            "after_sha": None,
            "merge_commit_sha": None,
            "status": "proposed",  # proposed -> applied -> rollback_proposed -> rolled_back
            "opened_at": datetime.now(UTC).isoformat(),
        }
        self.rollback_ledger.append(entry)
        self._save_rollback_ledger()
        return entry

    def set_autonomy_mode(self, mode: str) -> None:
        if mode not in ("propose_only", "auto_pr"):
            raise ValueError(f"Invalid autonomy_mode: {mode}")
        self.autonomy_mode = mode
        self._save_settings()

    def add_channel(self, data: dict) -> dict:
        import uuid

        channel = {
            "id": str(uuid.uuid4()),
            "name": data["name"],
            "type": data["type"],
            "url": data["url"],
            "severities": data["severities"],
            "enabled": data.get("enabled", True),
        }
        self.notification_channels.append(channel)
        self._save_settings()
        return channel

    def update_channel(self, channel_id: str, updates: dict) -> dict | None:
        for ch in self.notification_channels:
            if ch["id"] == channel_id:
                for key in ("name", "url", "severities", "enabled"):
                    if key in updates and updates[key] is not None:
                        ch[key] = updates[key]
                self._save_settings()
                return ch
        return None

    def delete_channel(self, channel_id: str) -> bool:
        before = len(self.notification_channels)
        self.notification_channels = [
            c for c in self.notification_channels if c["id"] != channel_id
        ]
        if len(self.notification_channels) != before:
            self._save_settings()
            return True
        return False


app_state = AppState()
