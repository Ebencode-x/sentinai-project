"""Database preparation that runs once when the application starts."""

from __future__ import annotations

import logging
import os

from src.db.bootstrap import bootstrap_default_account
from src.db.migrate import run_migrations

logger = logging.getLogger(__name__)

_OFF_VALUES = {"0", "false", "no", "off"}


def auto_migrate_enabled() -> bool:
    return os.getenv("SENTINAI_AUTO_MIGRATE", "1").strip().lower() not in _OFF_VALUES


def prepare_database() -> bool:
    """Apply migrations, then create the first admin if no account exists.

    Returns True on success. On failure the error is logged loudly and the
    application keeps serving (login will not work until the database is fixed),
    so a database outage at boot never takes the whole service down.
    Set SENTINAI_AUTO_MIGRATE=0 to manage migrations yourself.
    """
    if not auto_migrate_enabled():
        logger.info("[startup] SENTINAI_AUTO_MIGRATE is off - skipping migrations and bootstrap.")
        return True
    try:
        run_migrations()
        bootstrap_default_account()
    except Exception:
        logger.exception(
            "[startup] Database preparation FAILED. Login will not work until this is fixed. "
            "Check DATABASE_URL and that the database is reachable."
        )
        return False
    return True
