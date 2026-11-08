"""Startup checks for settings that only make sense together.

src.core.envparse rejects one bad value when a module is imported. This module
looks at the finished settings as a whole and reports every problem in one
message, so a single failed start shows the full list. A missing optional piece
is a warning, so a fresh clone with no .env still starts.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

from src.core.crypto import KEY_ENV, SecretKeyError, encrypt
from src.core.envparse import ConfigError

logger = logging.getLogger(__name__)

_REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_REAL_PROVIDERS = ("openai", "claude")


@dataclass
class EnvReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def check_env(cfg: Any) -> EnvReport:
    report = EnvReport()

    if cfg.llm_provider in _REAL_PROVIDERS and not cfg.llm_api_key.strip():
        report.errors.append(
            f"LLM_PROVIDER={cfg.llm_provider} needs LLM_API_KEY (or ANTHROPIC_API_KEY)"
        )

    repo = cfg.github_repo.strip()
    if repo and not _REPO_PATTERN.match(repo):
        report.errors.append(f"GITHUB_REPO={repo!r} is not in the form owner/name")
    if cfg.autonomy_mode == "auto_pr":
        if not cfg.github_token.strip():
            report.errors.append("AUTONOMY_MODE=auto_pr needs GITHUB_TOKEN")
        if not repo:
            report.errors.append("AUTONOMY_MODE=auto_pr needs GITHUB_REPO")

    try:
        encrypt("check")
    except SecretKeyError as exc:
        if os.getenv(KEY_ENV, "").strip():
            report.errors.append(str(exc))
        else:
            report.warnings.append(
                f"{KEY_ENV} is not set, so notification channels cannot be saved"
            )
    return report


def enforce_env(cfg: Any) -> EnvReport:
    """Log the warnings and raise ConfigError listing every error at once."""
    report = check_env(cfg)
    for warning in report.warnings:
        logger.warning("[startup] %s", warning)
    if report.errors:
        lines = "\n".join(f"  - {error}" for error in report.errors)
        raise ConfigError(f"Invalid configuration:\n{lines}")
    return report
