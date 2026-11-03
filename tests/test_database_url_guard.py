import os
import subprocess
import sys

import pytest


def import_session(request, database_url):
    env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
    if database_url is not None:
        env["DATABASE_URL"] = database_url
    return subprocess.run(
        [sys.executable, "-c", "import src.db.session"],
        cwd=request.config.rootpath,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_missing_database_url_is_rejected(request):
    result = import_session(request, None)
    assert result.returncode != 0
    assert "DATABASE_URL is not set" in result.stderr


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:///./sentinai.db",
        "sqlite:////app/data/sentinai.db",
        "postgres://user:pass@localhost:5432/db",
        "mysql://user:pass@localhost/db",
    ],
)
def test_non_postgres_url_is_rejected(request, url):
    result = import_session(request, url)
    assert result.returncode != 0
    assert "must start with postgresql" in result.stderr


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://user:pass@localhost:5432/db",
        "postgresql+psycopg2://user:pass@localhost:5432/db",
    ],
)
def test_postgres_url_is_accepted_without_connecting(request, url):
    result = import_session(request, url)
    assert result.returncode == 0, result.stderr
