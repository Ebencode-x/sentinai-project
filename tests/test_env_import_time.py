"""Import-time env limits: valid overrides apply, bad values fail with a clear error.

Each case runs in a fresh interpreter, so no module in this test process is
reloaded (other tests hold references to objects built at import time).
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _run(module: str, attr: str, var: str, value: str):
    env = {**os.environ, var: value}
    code = f"import importlib; m = importlib.import_module({module!r}); print(m.{attr})"
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.mark.parametrize(
    ("module", "attr", "var", "value", "expected"),
    [
        ("src.core.rate_limiter", "_LLM_MAX_PER_MINUTE", "SENTINAI_LLM_RATE_LIMIT", "25", "25"),
        (
            "src.services.resource_enforcer",
            "_HARD_MAX_MEMORY_MB",
            "SENTINAI_SANDBOX_MAX_MEMORY_MB",
            "512",
            "512",
        ),
        (
            "src.services.resource_enforcer",
            "_HARD_MAX_CPUS",
            "SENTINAI_SANDBOX_MAX_CPUS",
            "1.5",
            "1.5",
        ),
    ],
)
def test_valid_override_is_applied(module, attr, var, value, expected):
    result = _run(module, attr, var, value)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected


@pytest.mark.parametrize(
    ("module", "attr", "var", "value", "fragment"),
    [
        (
            "src.core.rate_limiter",
            "_PR_MAX_PER_MINUTE",
            "SENTINAI_PR_RATE_LIMIT",
            "abc",
            "whole number",
        ),
        (
            "src.services.resource_enforcer",
            "_HARD_MAX_TIMEOUT_S",
            "SENTINAI_SANDBOX_MAX_TIMEOUT_S",
            "ten",
            "whole number",
        ),
        ("src.core.rate_limiter", "_LLM_MAX_PER_MINUTE", "SENTINAI_LLM_RATE_LIMIT", "0", "minimum"),
        (
            "src.services.resource_enforcer",
            "_HARD_MAX_MEMORY_MB",
            "SENTINAI_SANDBOX_MAX_MEMORY_MB",
            "8",
            "minimum",
        ),
    ],
)
def test_bad_value_fails_naming_the_variable(module, attr, var, value, fragment):
    result = _run(module, attr, var, value)
    assert result.returncode != 0
    assert "ConfigError" in result.stderr
    assert var in result.stderr
    assert fragment in result.stderr
