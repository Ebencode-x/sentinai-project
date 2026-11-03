from unittest.mock import patch

import pytest

from src.integrations import github_client as gc
from src.integrations.llm_client import StubLLMClient
from src.services import remediation_engine as engine_mod


def make_client():
    with (
        patch.object(gc, "Github") as gh_cls,
        patch.object(gc, "settings") as fake_settings,
    ):
        fake_settings.github_token = "bad-token"
        fake_settings.github_repo = "org/repo"
        client = gc.GitHubClient()
    return client, gh_cls.return_value


def test_constructor_does_not_call_get_repo():
    client, gh = make_client()
    gh.get_repo.assert_not_called()
    assert client is not None


def test_repo_is_resolved_once_on_first_use():
    client, gh = make_client()
    first = client._repo
    second = client._repo
    gh.get_repo.assert_called_once_with("org/repo")
    assert first is second


def test_repo_can_be_replaced_for_tests():
    client, gh = make_client()
    sentinel = object()
    client._repo = sentinel
    assert client._repo is sentinel
    gh.get_repo.assert_not_called()


@pytest.mark.parametrize(
    ("token", "repo"),
    [("", "org/repo"), ("tok", ""), (None, None)],
)
def test_missing_config_is_rejected(token, repo):
    with patch.object(gc, "settings") as fake_settings:
        fake_settings.github_token = token
        fake_settings.github_repo = repo
        with pytest.raises(ValueError):
            gc.GitHubClient()


def test_engine_survives_client_failure():
    with (
        patch.object(engine_mod, "GitHubClient", side_effect=RuntimeError("401")),
        patch.object(engine_mod, "settings") as fake_settings,
    ):
        fake_settings.github_token = "bad-token"
        fake_settings.github_repo = "org/repo"
        engine = engine_mod.RemediationEngine(llm_client=StubLLMClient())
    assert engine.github_client is None
