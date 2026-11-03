"""Database engine and session factory."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.config import settings


def _require_postgres_url() -> str:
    url = (settings.database_url or "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. SentinAI needs a PostgreSQL URL such as "
            "postgresql+psycopg2://user:password@host:5432/dbname"
        )
    if not url.startswith("postgresql"):
        raise RuntimeError(
            "DATABASE_URL must start with postgresql:// or postgresql+psycopg2:// "
            "(SQLite is not supported)"
        )
    return url


engine = create_engine(_require_postgres_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a DB session, closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
