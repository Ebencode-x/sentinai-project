"""Shared in-memory state for the demo API."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.core.audit import AuditLogger, SessionFactory, audit_logger
from src.core.config import settings
from src.core.metrics import metrics
from src.db import repository
from src.db.session import SessionLocal
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
    session_factory: SessionFactory = field(default_factory=lambda: SessionLocal)
    persistence_errors: int = 0
    _account_id: str | None = None
    _scan_lock: threading.Lock = field(default_factory=threading.Lock)
    autonomy_mode: str = field(default_factory=lambda: settings.autonomy_mode)
    notification_channels: list[dict] = field(default_factory=list)
    rollback_ledger: list[dict] = field(default_factory=list)
    audit: AuditLogger = field(default_factory=lambda: audit_logger)
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
            outcome, account_id, incident_pk = self._store_incident(incident)
            if outcome == "repeat":
                continue

            suggestion = self.remediation_engine.suggest_fix(
                incident, autonomy_mode=self.autonomy_mode
            )
            if account_id and incident_pk:
                self._store_suggestion(account_id, incident_pk, suggestion)
            self._record_audit(incident, suggestion)

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

    def _record_audit(self, incident: LogIncident, suggestion: RemediationSuggestion) -> None:
        """Write one audit entry for a detected incident. Never breaks a scan."""
        try:
            self.audit.record(
                incident_id=incident.incident_id,
                model=suggestion.model or "unknown",
                provider=suggestion.source,
                patch_file=suggestion.patch_file,
                patch=suggestion.proposed_patch,
                policy_decision=None,
                risk_tier=None,
                review_required=suggestion.awaiting_approval,
                patch_applied=bool(suggestion.pr_url),
                tests_passed=None,
                pr_url=suggestion.pr_url,
                failure_reason=suggestion.provider_error,
                confidence=suggestion.confidence,
                source=suggestion.source,
            )
        except Exception:
            logger.exception("Audit record failed for incident %s", incident.incident_id)

    def _resolve_account_id(self, db) -> str | None:
        """Find, and remember, the account this deployment stores its data under."""
        if self._account_id is None:
            self._account_id = repository.default_account_id(db)
        return self._account_id

    def _store_incident(self, incident: LogIncident) -> tuple[str, str | None, str | None]:
        """Save an incident. Returns (outcome, account_id, incident_pk).

        The outcome is "new", "repeat" (already known, only counted) or "unstored"
        when the database could not be used. An unstored incident is still analysed
        and notified, so a database problem never silences an alert.
        """
        try:
            with self.session_factory() as db:
                account_id = self._resolve_account_id(db)
                if account_id is None:
                    raise RuntimeError("no account exists yet")
                incident_pk = repository.insert_incident_if_new(db, account_id, incident)
        except Exception:
            self.persistence_errors += 1
            logger.exception("[state] Could not store incident %s", incident.incident_id)
            return "unstored", None, None
        return ("new" if incident_pk else "repeat"), account_id, incident_pk

    def _store_suggestion(
        self, account_id: str, incident_pk: str, suggestion: RemediationSuggestion
    ) -> None:
        try:
            with self.session_factory() as db:
                repository.add_suggestion(db, account_id, incident_pk, suggestion)
        except Exception:
            self.persistence_errors += 1
            logger.exception("[state] Could not store suggestion %s", suggestion.id)

    def incidents(self) -> list[LogIncident]:
        """The latest incidents, oldest first."""
        with self.session_factory() as db:
            account_id = self._resolve_account_id(db)
            if account_id is None:
                return []
            return repository.list_incidents(db, account_id, settings.max_recent_incidents)

    def suggestions(self) -> list[RemediationSuggestion]:
        """The latest suggestions, oldest first."""
        with self.session_factory() as db:
            account_id = self._resolve_account_id(db)
            if account_id is None:
                return []
            return repository.list_suggestions(db, account_id, settings.max_recent_incidents)

    def latest_suggestion(self) -> RemediationSuggestion | None:
        with self.session_factory() as db:
            account_id = self._resolve_account_id(db)
            if account_id is None:
                return None
            return repository.latest_suggestion(db, account_id)

    def stats_snapshot(self) -> dict:
        """Lightweight runtime metrics for demos and observability export."""
        by_source: dict[str, int] = {"stub": 0, "provider": 0, "fallback": 0}
        incident_count = 0
        suggestion_count = 0
        reachable = True
        try:
            with self.session_factory() as db:
                account_id = self._resolve_account_id(db)
                if account_id is not None:
                    found = repository.counts(db, account_id)
                    incident_count = found["incidents"]
                    suggestion_count = found["suggestions"]
                    for key, total in found["by_source"].items():
                        if key in by_source:
                            by_source[key] = total
        except Exception:
            reachable = False
            logger.warning("[state] Stats could not read the database", exc_info=True)

        return {
            "service": "sentinai",
            "log_file_path": settings.log_file_path,
            "llm_provider": settings.llm_provider,
            "buffer_incident_count": incident_count,
            "buffer_suggestion_count": suggestion_count,
            "dedupe_fingerprints_tracked": incident_count,
            "dedupe_window_max": settings.incident_dedupe_window,
            "total_scan_runs": self.total_scan_runs,
            "last_scan_at_utc": self.last_scan_at_utc.isoformat()
            if self.last_scan_at_utc
            else None,
            "last_scan_new_incidents": self.last_scan_new_incidents,
            "recent_suggestions_by_source": by_source,
            "persistence_errors": self.persistence_errors,
            "database_reachable": reachable,
            "llm_metrics": metrics.snapshot(),
        }

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

    def get_rollback_ledger_entry(self, ledger_id: str) -> dict | None:
        for entry in self.rollback_ledger:
            if entry["id"] == ledger_id:
                return entry
        return None

    def propose_rollback(self, ledger_id: str) -> dict:
        entry = self.get_rollback_ledger_entry(ledger_id)
        if entry is None:
            raise ValueError("Ledger entry not found.")
        github = self.remediation_engine.github_client
        if github is None:
            raise ValueError("GitHub integration not configured.")

        if entry.get("merge_commit_sha") is None:
            merge_info = github.check_pr_merged(entry["pr_number"])
            if merge_info is None:
                raise ValueError("PR has not been merged yet — nothing to roll back.")
            entry["merge_commit_sha"] = merge_info["merge_commit_sha"]
            after_sha = github.get_current_file_sha(entry["patch_file"], ref=entry["branch_name"])
            entry["after_sha"] = after_sha
            entry["status"] = "applied"

        current_sha = github.get_current_file_sha(entry["patch_file"])
        if current_sha is None:
            raise ValueError(f"Could not read current state of {entry['patch_file']}.")

        if current_sha != entry["after_sha"]:
            entry["status"] = "rollback_blocked"
            self._save_rollback_ledger()
            return {
                "conflict": True,
                "ledger_id": ledger_id,
                "patch_file": entry["patch_file"],
                "after_sha": entry["after_sha"],
                "current_sha": current_sha,
                "message": (
                    f"{entry['patch_file']} has changed since this patch was applied "
                    "(another patch or a manual commit). Auto-revert blocked."
                ),
            }

        entry["status"] = "rollback_proposed"
        entry["rollback_current_sha"] = current_sha
        self._save_rollback_ledger()
        return {
            "conflict": False,
            "ledger_id": ledger_id,
            "patch_file": entry["patch_file"],
            "message": "Clean revert available. Call confirm to execute.",
        }

    def confirm_rollback(self, ledger_id: str) -> dict:
        entry = self.get_rollback_ledger_entry(ledger_id)
        if entry is None:
            raise ValueError("Ledger entry not found.")
        if entry.get("status") != "rollback_proposed":
            raise ValueError(
                f"Ledger entry status is '{entry.get('status')}', expected 'rollback_proposed'. "
                "Call propose first."
            )
        github = self.remediation_engine.github_client
        if github is None:
            raise ValueError("GitHub integration not configured.")

        new_sha = github.revert_patch(
            patch_file=entry["patch_file"],
            before_sha=entry["before_sha"],
            current_sha=entry["rollback_current_sha"],
            incident_id=entry["incident_id"],
        )
        if new_sha is None:
            raise ValueError("Revert commit failed. Check server logs.")

        entry["status"] = "rolled_back"
        entry["revert_commit_sha"] = new_sha
        self._save_rollback_ledger()
        return {"ledger_id": ledger_id, "status": "rolled_back", "revert_commit_sha": new_sha}

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
