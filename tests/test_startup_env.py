"""A bad combination of settings stops the app from starting and names every problem.

Each case runs in a fresh interpreter. Only failing combinations are tested here,
because they stop before the database is touched.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_CLEARED = {
    "GITHUB_TOKEN",
    "GITHUB_REPO",
    "LLM_API_KEY",
    "ANTHROPIC_API_KEY",
    "AUTONOMY_MODE",
    "LLM_PROVIDER",
}
_CODE = (
    "from fastapi.testclient import TestClient\n"
    "import src.main\n"
    "with TestClient(src.main.app):\n"
    "    print('started')\n"
)


def _start(tmp_path, **extra):
    env = {k: v for k, v in os.environ.items() if k not in _CLEARED}
    env["SENTINAI_ENV_FILE"] = str(tmp_path / "missing.env")
    env.update(extra)
    return subprocess.run(
        [sys.executable, "-c", _CODE],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_auto_pr_without_github_settings_does_not_start(tmp_path):
    result = _start(tmp_path, AUTONOMY_MODE="auto_pr")
    assert result.returncode != 0
    assert "ConfigError" in result.stderr
    assert "GITHUB_TOKEN" in result.stderr
    assert "GITHUB_REPO" in result.stderr
    assert "started" not in result.stdout


def test_real_provider_without_key_does_not_start(tmp_path):
    result = _start(tmp_path, LLM_PROVIDER="claude")
    assert result.returncode != 0
    assert "LLM_API_KEY" in result.stderr
    assert "started" not in result.stdout
