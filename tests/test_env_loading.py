"""One place loads .env, and SENTINAI_ENV_FILE is honoured everywhere.

Run from the repository root (the last test reads files by relative path).
"""

import os
from pathlib import Path

import pytest

from src.core.env import env_file, load_env

VAR = "SENTINAI_TEST_ENV_LOADING"


@pytest.fixture(autouse=True)
def clean_var(monkeypatch):
    monkeypatch.delenv(VAR, raising=False)
    yield
    os.environ.pop(VAR, None)


def test_env_file_follows_the_override(monkeypatch, tmp_path):
    target = tmp_path / "custom.env"
    monkeypatch.setenv("SENTINAI_ENV_FILE", str(target))
    assert env_file() == target


def test_env_file_defaults_to_the_project_root(monkeypatch):
    monkeypatch.delenv("SENTINAI_ENV_FILE", raising=False)
    assert env_file().name == ".env"


def test_load_env_reads_the_chosen_file(monkeypatch, tmp_path):
    target = tmp_path / "custom.env"
    target.write_text(f"{VAR}=from-file\n")
    monkeypatch.setenv("SENTINAI_ENV_FILE", str(target))
    load_env()
    assert os.environ.get(VAR) == "from-file"


def test_load_env_with_a_missing_file_does_nothing(monkeypatch, tmp_path):
    monkeypatch.setenv("SENTINAI_ENV_FILE", str(tmp_path / "missing.env"))
    load_env()
    assert VAR not in os.environ


@pytest.mark.parametrize("name", ["src/main.py", "alembic/env.py"])
def test_no_direct_dotenv_loading_outside_src_core_env(name):
    assert "load_dotenv(" not in Path(name).read_text()
