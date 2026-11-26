"""Guards the Docker image against shipping without its patch policy.

The policy engine loads sentinai-policy.yml from the app root. If the final
Docker stage stops copying it, production would run without the policy.
"""

import re

from src.services.policy_engine import _DEFAULT_POLICY

ROOT = _DEFAULT_POLICY.parent
POLICY_COPY = r"(?m)^COPY\s+sentinai-policy\.yml\s+\./sentinai-policy\.yml\s*$"
SRC_COPY = r"(?m)^COPY\s+src\s+\./src\s*$"


def _final_stage() -> str:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    return re.split(r"(?m)^FROM ", text)[-1]


def test_policy_file_exists_at_app_root() -> None:
    assert _DEFAULT_POLICY.is_file()


def test_final_stage_copies_policy_next_to_src() -> None:
    stage = _final_stage()
    assert re.search(POLICY_COPY, stage)
    assert re.search(SRC_COPY, stage)


def test_dockerignore_does_not_exclude_policy() -> None:
    ignore = ROOT / ".dockerignore"
    if ignore.exists():
        lines = [x.strip() for x in ignore.read_text(encoding="utf-8").splitlines()]
        assert "sentinai-policy.yml" not in lines
