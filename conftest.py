"""Shared test setup: every test runs against Postgres, never SQLite."""

import os
import sys
import uuid

sys.path.insert(0, os.getcwd())

import pytest  # noqa: E402
from dotenv import dotenv_values  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

# Read only the one key we need. Never load the whole .env into the test process:
# it holds real tokens (GitHub, LLM) that tests must not be able to use.
_BASE_URL = (
    os.getenv("TEST_DATABASE_URL")
    or dotenv_values(".env").get("TEST_DATABASE_URL")
    or os.getenv("DATABASE_URL", "")
)
if _BASE_URL.startswith("postgresql"):
    # Must happen before any src module reads its settings.
    os.environ["DATABASE_URL"] = _BASE_URL


@pytest.fixture
def pg_url():
    """A throwaway Postgres schema for one test, returned as a database URL."""
    if not _BASE_URL.startswith("postgresql"):
        pytest.fail("Set TEST_DATABASE_URL to a Postgres database to run these tests.")
    schema = "t_" + uuid.uuid4().hex[:12]
    admin = create_engine(_BASE_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    url = make_url(_BASE_URL).update_query_dict({"options": f"-csearch_path={schema}"})
    yield url.render_as_string(hide_password=False)
    with admin.connect() as conn:
        conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    admin.dispose()


@pytest.fixture
def pg_engine(pg_url):
    """An engine bound to a fresh schema, for tests that build tables themselves."""
    engine = create_engine(pg_url)
    yield engine
    engine.dispose()


@pytest.fixture
def app_db(pg_url):
    """A migrated throwaway schema holding one account. Yields (session_factory, account_id)."""
    from sqlalchemy.orm import sessionmaker

    from src.db.migrate import run_migrations
    from src.db.models import Account

    run_migrations(pg_url)
    engine = create_engine(pg_url)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as db:
        account = Account(name="test account")
        db.add(account)
        db.commit()
        account_id = account.id
    yield factory, account_id
    engine.dispose()
