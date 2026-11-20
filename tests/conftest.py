"""Test defaults, loaded by pytest before any test module is imported."""

import os

import pytest

# src.db.session needs a PostgreSQL URL at import time. CI and the smoke test set
# their own DATABASE_URL, which setdefault leaves alone. The engine is lazy, so
# nothing connects at import.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg2://sentinai:sentinai@localhost:5432/sentinai_test",
)


@pytest.fixture(autouse=True)
def _reset_llm_breakers():
    """The breaker registry is process-wide, so keep each test independent."""
    from sentinai.llm.breaker import reset_breakers  # noqa: PLC0415

    reset_breakers()
    yield
    reset_breakers()
