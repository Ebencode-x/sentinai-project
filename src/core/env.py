"""Load the local .env file, from one place only.

SENTINAI_ENV_FILE points at another file (the fresh-start smoke test sets it to a
missing file). Without it the .env at the project root is used, as before.
Variables already set in the environment are never overridden.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent.parent


def env_file() -> Path:
    return Path(os.environ.get("SENTINAI_ENV_FILE") or _ROOT / ".env")


def load_env() -> None:
    load_dotenv(env_file())
