from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet

from src.core.crypto import KEY_ENV
from src.core.env_check import check_env, enforce_env
from src.core.envparse import ConfigError


def make(**overrides):
    values = {
        "llm_provider": "stub",
        "llm_api_key": "",
        "github_token": "",
        "github_repo": "",
        "autonomy_mode": "propose_only",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture(autouse=True)
def valid_key(monkeypatch):
    monkeypatch.setenv(KEY_ENV, Fernet.generate_key().decode())


def test_defaults_are_clean():
    report = check_env(make())
    assert report.errors == []
    assert report.warnings == []


def test_real_provider_without_key_is_an_error():
    report = check_env(make(llm_provider="claude"))
    assert any("LLM_API_KEY" in error for error in report.errors)


def test_real_provider_with_key_is_fine():
    assert check_env(make(llm_provider="openai", llm_api_key="k")).errors == []


def test_auto_pr_needs_token_and_repo():
    report = check_env(make(autonomy_mode="auto_pr"))
    assert len(report.errors) == 2


def test_auto_pr_with_token_and_repo_is_fine():
    cfg = make(autonomy_mode="auto_pr", github_token="t", github_repo="Ebencode-x/sentinai-project")
    assert check_env(cfg).errors == []


@pytest.mark.parametrize("repo", ["sentinai", "a/b/c", "owner /name", "https://github.com/a/b"])
def test_bad_repo_format_is_an_error(repo):
    report = check_env(make(github_repo=repo))
    assert any("owner/name" in error for error in report.errors)


def test_malformed_secret_key_is_an_error(monkeypatch):
    monkeypatch.setenv(KEY_ENV, "not-a-key")
    report = check_env(make())
    assert any("Fernet" in error for error in report.errors)


def test_missing_secret_key_is_only_a_warning(monkeypatch):
    monkeypatch.delenv(KEY_ENV, raising=False)
    report = check_env(make())
    assert report.errors == []
    assert any(KEY_ENV in warning for warning in report.warnings)


def test_enforce_lists_every_problem_at_once():
    with pytest.raises(ConfigError) as info:
        enforce_env(make(llm_provider="claude", autonomy_mode="auto_pr"))
    message = str(info.value)
    assert "LLM_API_KEY" in message
    assert "GITHUB_TOKEN" in message
    assert "GITHUB_REPO" in message
