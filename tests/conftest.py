"""Test defaults, loaded by pytest before any test module is imported."""

import os

# src.db.session needs a PostgreSQL URL at import time. CI and the smoke test set
# their own DATABASE_URL, which setdefault leaves alone. The engine is lazy, so
# nothing connects at import.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg2://sentinai:sentinai@localhost:5432/sentinai_test",
)
