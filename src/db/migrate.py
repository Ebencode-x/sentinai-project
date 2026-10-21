"""Run Alembic migrations from inside the application."""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config

from alembic import command

_ROOT = Path(__file__).resolve().parent.parent.parent


def run_migrations(database_url: str | None = None) -> None:
    """Upgrade the database to the latest schema revision.

    Safe to call on every start: when the schema is already current this does
    nothing. ``database_url`` overrides ``settings.database_url`` (used by tests).
    """
    cfg = Config(str(_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_ROOT / "alembic"))
    cfg.attributes["configure_logger"] = False
    if database_url:
        cfg.attributes["database_url"] = database_url
    command.upgrade(cfg, "head")
