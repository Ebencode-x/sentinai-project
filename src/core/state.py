"""Shared in-memory state for the demo API."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.core.audit import AuditLogger, SessionFactory, audit_logger
from src.core.config import settings
from src.core.crypto import KEY_ENV, MASK_MARK, SecretKeyError, decrypt, encrypt, mask_url
from src.core.metrics import metrics
from src.db import repository
from src.db.session import SessionLocal
from src.integrations.notifier import notify
from src.models.events import LogIncident, RemediationSuggestion
from src.services.remediation_engine import RemediationEngine
from src.services.watcher import LogWatcher, WatcherConfig

logger = logging.getLogger(__name__)

AUTONOMY_MODES = ("propose_only", "auto_pr")


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
                incident, autonomy_mode=self.current_autonomy_mode()
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
            notify(incident, suggestion, channels=self.delivery_channels())

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

        return pathlib.Path(self.watcher.config.log_file_path).parent / "settings.json"

    def load_settings(self) -> None:
        """Read settings from the database and import a leftover settings.json once."""
        try:
            self.current_autonomy_mode()
            self._import_legacy_settings()
        except Exception:
            logger.warning("[state] Failed to load settings", exc_info=True)

    def _import_legacy_settings(self) -> None:
        """Move an old settings.json into the database, then delete it (it holds secrets)."""
        import json

        path = self._settings_cache_path()
        if not path.exists():
            return
        data = json.loads(path.read_text())
        found = data.get("notification_channels")
        legacy = [c for c in found if isinstance(c, dict)] if isinstance(found, list) else []
        if legacy:
            try:
                encrypt("probe")
            except SecretKeyError:
                logger.warning(
                    "[state] settings.json holds channels but %s is not set; leaving it in place",
                    KEY_ENV,
                )
                return
        with self.session_factory() as db:
            account_id = self._require_account_id(db)
            if repository.get_autonomy_mode(db, account_id) is None:
                mode = data.get("autonomy_mode")
                if mode in AUTONOMY_MODES:
                    repository.set_autonomy_mode(db, account_id, mode, "settings.json import")
            known = {row.name for row in repository.list_channels(db, account_id)}
            for channel in legacy:
                if channel.get("name") in known or not channel.get("url"):
                    continue
                if channel.get("type") not in ("slack", "webhook"):
                    continue
                repository.add_channel(
                    db,
                    account_id,
                    name=channel["name"],
                    type_=channel["type"],
                    url_encrypted=encrypt(channel["url"]),
                    severities=list(channel.get("severities", [])),
                    enabled=bool(channel.get("enabled", True)),
                )
        path.unlink()
        logger.info("[state] Imported settings.json into the database and removed the file")

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

    def _require_account_id(self, db) -> str:
        account_id = self._resolve_account_id(db)
        if account_id is None:
            raise RuntimeError("No account exists yet.")
        return account_id

    def current_autonomy_mode(self) -> str:
        """The mode stored for the account, or the last known one if the database fails.

        A failed read is logged but not counted in persistence_errors, which tracks
        incidents and suggestions that could not be saved.
        """
        try:
            with self.session_factory() as db:
                account_id = self._resolve_account_id(db)
                stored = repository.get_autonomy_mode(db, account_id) if account_id else None
            if stored in AUTONOMY_MODES:
                self.autonomy_mode = stored
        except Exception:
            logger.warning(
                "[state] Could not read autonomy_mode, using %s", self.autonomy_mode, exc_info=True
            )
        return self.autonomy_mode

    def set_autonomy_mode(self, mode: str) -> None:
        if mode not in AUTONOMY_MODES:
            raise ValueError(f"Invalid autonomy_mode: {mode}")
        with self.session_factory() as db:
            account_id = self._require_account_id(db)
            repository.set_autonomy_mode(db, account_id, mode)
        self.autonomy_mode = mode

    @staticmethod
    def _channel_view(row, url: str) -> dict:
        return {
            "id": row.id,
            "name": row.name,
            "type": row.type,
            "url": url,
            "severities": list(row.severities or []),
            "enabled": row.enabled,
        }

    @staticmethod
    def _masked_url(row) -> str:
        try:
            return mask_url(decrypt(row.url_encrypted))
        except SecretKeyError:
            return "(encrypted)"

    def channels(self) -> list[dict]:
        """Channels for the API. URLs are masked, so a secret never leaves the server."""
        with self.session_factory() as db:
            account_id = self._resolve_account_id(db)
            if account_id is None:
                return []
            rows = repository.list_channels(db, account_id)
            return [self._channel_view(row, self._masked_url(row)) for row in rows]

    def delivery_channels(self) -> list[dict]:
        """Channels with their real URLs, used only to send notifications. Never raises."""
        try:
            with self.session_factory() as db:
                account_id = self._resolve_account_id(db)
                if account_id is None:
                    return []
                found = []
                for row in repository.list_channels(db, account_id):
                    try:
                        found.append(self._channel_view(row, decrypt(row.url_encrypted)))
                    except SecretKeyError:
                        logger.warning(
                            "[state] Skipping channel %s: cannot decrypt its URL", row.name
                        )
                return found
        except Exception:
            logger.warning("[state] Could not load notification channels", exc_info=True)
            return []

    def add_channel(self, data: dict) -> dict:
        token = encrypt(data["url"])  # raises SecretKeyError before the database is touched
        with self.session_factory() as db:
            account_id = self._require_account_id(db)
            row = repository.add_channel(
                db,
                account_id,
                name=data["name"],
                type_=data["type"],
                url_encrypted=token,
                severities=list(data["severities"]),
                enabled=data.get("enabled", True),
            )
            return self._channel_view(row, mask_url(data["url"]))

    def update_channel(self, channel_id: str, updates: dict) -> dict | None:
        with self.session_factory() as db:
            account_id = self._require_account_id(db)
            row = repository.get_channel(db, account_id, channel_id)
            if row is None:
                return None
            for key in ("name", "severities", "enabled"):
                value = updates.get(key)
                if value is not None:
                    setattr(row, key, list(value) if key == "severities" else value)
            new_url = updates.get("url")
            # A masked URL sent back by a client must never replace the real one.
            if new_url is not None and MASK_MARK not in new_url:
                row.url_encrypted = encrypt(new_url)
            db.commit()
            return self._channel_view(row, self._masked_url(row))

    def delete_channel(self, channel_id: str) -> bool:
        with self.session_factory() as db:
            account_id = self._require_account_id(db)
            return repository.delete_channel(db, account_id, channel_id)


app_state = AppState()
