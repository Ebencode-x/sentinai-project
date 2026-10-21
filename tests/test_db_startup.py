"""A fresh database must become usable on its own: migrations, first admin, login."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from src.db.bootstrap import DEFAULT_ADMIN_EMAIL, bootstrap_default_account
from src.db.migrate import run_migrations
from src.db.models import Account, User
from src.db.session import get_db
from src.db.startup import prepare_database
from src.main import app


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """An empty SQLite file, migrated to the latest schema."""
    url = f"sqlite:///{tmp_path / 'fresh.db'}"
    run_migrations(url)
    engine = create_engine(url, connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.delenv("SENTINAI_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("SENTINAI_ADMIN_PASSWORD", raising=False)
    yield factory
    engine.dispose()


def test_migrations_create_the_auth_tables(tmp_path):
    url = f"sqlite:///{tmp_path / 'm.db'}"
    run_migrations(url)
    tables = set(inspect(create_engine(url)).get_table_names())
    assert {"accounts", "users", "sessions"} <= tables


def test_migrations_are_idempotent(tmp_path):
    url = f"sqlite:///{tmp_path / 'm.db'}"
    run_migrations(url)
    run_migrations(url)  # second run must be a harmless no-op


def test_migrations_do_not_replace_app_logging(tmp_path):
    root_handlers = list(logging.getLogger().handlers)
    app_logger = logging.getLogger("src.some.module")
    run_migrations(f"sqlite:///{tmp_path / 'm.db'}")
    assert logging.getLogger().handlers == root_handlers
    assert not app_logger.disabled


def test_bootstrap_uses_configured_admin(fresh_db, monkeypatch):
    monkeypatch.setenv("SENTINAI_ADMIN_EMAIL", "boss@example.com")
    monkeypatch.setenv("SENTINAI_ADMIN_PASSWORD", "correct-horse-battery")
    bootstrap_default_account(fresh_db)
    with fresh_db() as db:
        assert db.query(Account).count() == 1
        assert db.query(User).one().email == "boss@example.com"


def test_bootstrap_generates_a_one_time_password_when_unset(fresh_db, caplog):
    with caplog.at_level(logging.WARNING):
        bootstrap_default_account(fresh_db)
    with fresh_db() as db:
        assert db.query(User).one().email == DEFAULT_ADMIN_EMAIL
    assert "FIRST-RUN ADMIN LOGIN" in caplog.text


def test_bootstrap_is_idempotent_and_does_not_reprint_secret(fresh_db, caplog):
    bootstrap_default_account(fresh_db)
    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        bootstrap_default_account(fresh_db)
    with fresh_db() as db:
        assert db.query(Account).count() == 1
    assert "FIRST-RUN ADMIN LOGIN" not in caplog.text


def test_fresh_database_can_log_in_and_use_the_api(fresh_db, monkeypatch):
    """The scenario a newcomer hits: empty DB, set admin, log in, call a protected route."""
    monkeypatch.setenv("SENTINAI_ADMIN_EMAIL", "boss@example.com")
    monkeypatch.setenv("SENTINAI_ADMIN_PASSWORD", "correct-horse-battery")
    bootstrap_default_account(fresh_db)

    def _get_db():
        db = fresh_db()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    try:
        client = TestClient(app)
        bad = client.post("/api/auth/login", json={"email": "boss@example.com", "password": "nope"})
        assert bad.status_code == 401

        ok = client.post(
            "/api/auth/login",
            json={"email": "boss@example.com", "password": "correct-horse-battery"},
        )
        assert ok.status_code == 200
        token = ok.json()["token"]

        no_token = client.get("/api/incidents")
        assert no_token.status_code == 401
        with_token = client.get("/api/incidents", headers={"X-Session-Token": token})
        assert with_token.status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_prepare_database_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("SENTINAI_AUTO_MIGRATE", "0")
    assert prepare_database() is True


def test_prepare_database_survives_a_broken_database(monkeypatch):
    monkeypatch.delenv("SENTINAI_AUTO_MIGRATE", raising=False)

    def boom(*_a, **_k):
        raise RuntimeError("database unreachable")

    monkeypatch.setattr("src.db.startup.run_migrations", boom)
    assert prepare_database() is False  # logged, but the app is not taken down


def test_session_expiry_works_with_naive_datetimes_from_sqlite():
    """SQLite returns naive datetimes; the expiry check must treat them as UTC."""
    from datetime import UTC, datetime, timedelta

    from src.db.models import Session as SessionModel

    future = (datetime.now(UTC) + timedelta(hours=1)).replace(tzinfo=None)
    past = (datetime.now(UTC) - timedelta(hours=1)).replace(tzinfo=None)
    assert SessionModel(user_id="u", expires_at=future).is_expired is False
    assert SessionModel(user_id="u", expires_at=past).is_expired is True


def test_login_response_expiry_is_timezone_aware(fresh_db, monkeypatch):
    monkeypatch.setenv("SENTINAI_ADMIN_EMAIL", "boss@example.com")
    monkeypatch.setenv("SENTINAI_ADMIN_PASSWORD", "correct-horse-battery")
    bootstrap_default_account(fresh_db)

    def _get_db():
        db = fresh_db()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    try:
        res = TestClient(app).post(
            "/api/auth/login",
            json={"email": "boss@example.com", "password": "correct-horse-battery"},
        )
        assert res.status_code == 200
        assert res.json()["expires_at"].endswith("+00:00")
    finally:
        app.dependency_overrides.pop(get_db, None)
