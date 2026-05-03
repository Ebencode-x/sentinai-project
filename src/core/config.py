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
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "")
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "25"))


settings = Settings()

