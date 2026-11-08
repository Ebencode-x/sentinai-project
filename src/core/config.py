"""Central runtime configuration for SentinAI."""

from __future__ import annotations

import os
from dataclasses import dataclass

from src.core.envparse import env_choice, env_float, env_int

AUTONOMY_MODES = ("propose_only", "auto_pr")
LLM_PROVIDERS = ("stub", "openai", "claude")


@dataclass
class Settings:
    """Environment-backed application settings."""

    app_name: str = os.getenv("APP_NAME", "SentinAI")
    log_file_path: str = os.getenv("LOG_FILE_PATH", "logs/app.log")
    max_recent_incidents: int = env_int("MAX_RECENT_INCIDENTS", 100, minimum=1)
    llm_provider: str = env_choice("LLM_PROVIDER", "stub", LLM_PROVIDERS)
    llm_api_key: str = os.getenv("LLM_API_KEY", "") or os.getenv("ANTHROPIC_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "")
    llm_timeout_seconds: float = env_float("LLM_TIMEOUT_SECONDS", 25.0, minimum=0.1)
    llm_max_retries: int = env_int("LLM_MAX_RETRIES", 3, minimum=0)
    llm_retry_backoff_seconds: float = env_float("LLM_RETRY_BACKOFF_SECONDS", 1.0, minimum=0.0)
    incident_dedupe_window: int = env_int("INCIDENT_DEDUPE_WINDOW", 200, minimum=1)
    github_token: str = os.getenv("GITHUB_TOKEN", "")
    github_repo: str = os.getenv("GITHUB_REPO", "")
    autonomy_mode: str = env_choice("AUTONOMY_MODE", "propose_only", AUTONOMY_MODES)

    cors_origins: str = os.getenv("SENTINAI_CORS_ORIGINS", "")  # comma-separated
    database_url: str = os.getenv("DATABASE_URL", "")


settings = Settings()
