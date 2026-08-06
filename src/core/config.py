"""Central runtime configuration for SentinAI."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Settings:
    """Environment-backed application settings."""

    app_name: str = os.getenv("APP_NAME", "SentinAI")
    log_file_path: str = os.getenv("LOG_FILE_PATH", "logs/app.log")
    max_recent_incidents: int = int(os.getenv("MAX_RECENT_INCIDENTS", "100"))
    llm_provider: str = os.getenv("LLM_PROVIDER", "stub")
    llm_api_key: str = os.getenv("LLM_API_KEY", "") or os.getenv("ANTHROPIC_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "")
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "25"))
    llm_max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "3"))
    llm_retry_backoff_seconds: float = float(os.getenv("LLM_RETRY_BACKOFF_SECONDS", "1.0"))
    incident_dedupe_window: int = int(os.getenv("INCIDENT_DEDUPE_WINDOW", "200"))
    github_token: str = os.getenv("GITHUB_TOKEN", "")
    github_repo: str = os.getenv("GITHUB_REPO", "")
    autonomy_mode: str = os.getenv("AUTONOMY_MODE", "propose_only")

    cors_origins: str = os.getenv("SENTINAI_CORS_ORIGINS", "")  # comma-separated
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./sentinai.db")


settings = Settings()
