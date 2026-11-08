"""Settings and notifier env values: valid ones apply, bad ones fail clearly.

Each case runs in a fresh interpreter, so no module in this test process is
reloaded (other tests hold references to objects built at import time).
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _run(module: str, expr: str, var: str, value: str):
    env = {**os.environ, var: value}
    code = f"import importlib; m = importlib.import_module({module!r}); print(m.{expr})"
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.mark.parametrize(
    ("module", "expr", "var", "value", "expected"),
    [
        ("src.core.config", "settings.autonomy_mode", "AUTONOMY_MODE", "AUTO_PR", "auto_pr"),
        ("src.core.config", "settings.llm_provider", "LLM_PROVIDER", " Claude ", "claude"),
        ("src.core.config", "settings.llm_max_retries", "LLM_MAX_RETRIES", "0", "0"),
        (
            "src.integrations.notifier",
            "NOTIFICATION_TIMEOUT",
            "NOTIFICATION_TIMEOUT_SECONDS",
            "3.5",
            "3.5",
        ),
    ],
)
def test_valid_value_is_applied(module, expr, var, value, expected):
    result = _run(module, expr, var, value)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected


@pytest.mark.parametrize(
    ("module", "var", "value", "fragment"),
    [
        ("src.core.config", "AUTONOMY_MODE", "auto-pr", "is not one of"),
        ("src.core.config", "LLM_PROVIDER", "anthropic", "is not one of"),
        ("src.core.config", "LLM_TIMEOUT_SECONDS", "soon", "not a number"),
        ("src.core.config", "INCIDENT_DEDUPE_WINDOW", "0", "minimum"),
        ("src.integrations.notifier", "NOTIFICATION_TIMEOUT_SECONDS", "0", "minimum"),
    ],
)
def test_bad_value_fails_naming_the_variable(module, var, value, fragment):
    result = _run(module, "__name__", var, value)
    assert result.returncode != 0
    assert "ConfigError" in result.stderr
    assert var in result.stderr
    assert fragment in result.stderr


def test_autonomy_modes_have_one_definition():
    from src.core import config, state

    assert state.AUTONOMY_MODES is config.AUTONOMY_MODES
