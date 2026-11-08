"""Typed environment parsing: defaults, bad values and error messages."""

import pytest

from src.core.envparse import ConfigError, env_choice, env_float, env_int

NAME = "SENTINAI_TEST_VALUE"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv(NAME, raising=False)


def test_unset_returns_default():
    assert env_int(NAME, 7) == 7
    assert env_float(NAME, 1.5) == 1.5
    assert env_choice(NAME, "a", {"a", "b"}) == "a"


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_counts_as_unset(monkeypatch, blank):
    monkeypatch.setenv(NAME, blank)
    assert env_int(NAME, 7) == 7
    assert env_float(NAME, 1.5) == 1.5
    assert env_choice(NAME, "a", {"a", "b"}) == "a"


def test_valid_values_are_parsed_and_stripped(monkeypatch):
    monkeypatch.setenv(NAME, " 12 ")
    assert env_int(NAME, 7) == 12
    monkeypatch.setenv(NAME, " 2.5 ")
    assert env_float(NAME, 1.0) == 2.5


@pytest.mark.parametrize("bad", ["abc", "1.5", "10x"])
def test_int_rejects_non_integers(monkeypatch, bad):
    monkeypatch.setenv(NAME, bad)
    with pytest.raises(ConfigError) as info:
        env_int(NAME, 7)
    assert NAME in str(info.value)
    assert repr(bad) in str(info.value)


@pytest.mark.parametrize("bad", ["abc", "nan", "inf", "-inf"])
def test_float_rejects_non_finite_and_text(monkeypatch, bad):
    monkeypatch.setenv(NAME, bad)
    with pytest.raises(ConfigError) as info:
        env_float(NAME, 1.0)
    assert NAME in str(info.value)


def test_range_is_enforced(monkeypatch):
    monkeypatch.setenv(NAME, "0")
    with pytest.raises(ConfigError, match="minimum"):
        env_int(NAME, 5, minimum=1)
    monkeypatch.setenv(NAME, "999")
    with pytest.raises(ConfigError, match="maximum"):
        env_int(NAME, 5, maximum=100)
    with pytest.raises(ConfigError, match="maximum"):
        env_float(NAME, 5.0, maximum=100.0)
    monkeypatch.setenv(NAME, "1")
    assert env_int(NAME, 5, minimum=1, maximum=100) == 1


def test_choice_is_case_insensitive(monkeypatch):
    monkeypatch.setenv(NAME, " Propose_Only ")
    assert env_choice(NAME, "stub", {"stub", "propose_only"}) == "propose_only"


def test_choice_rejects_unknown_and_lists_allowed(monkeypatch):
    monkeypatch.setenv(NAME, "fullauto")
    with pytest.raises(ConfigError) as info:
        env_choice(NAME, "stub", {"stub", "propose_only"})
    message = str(info.value)
    assert NAME in message
    assert "fullauto" in message
    assert "propose_only, stub" in message


def test_config_error_is_a_value_error():
    assert issubclass(ConfigError, ValueError)
