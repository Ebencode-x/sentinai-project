"""FastAPI entrypoint for SentinAI."""

from __future__ import annotations

from fastapi import FastAPI

from src.api.routes import router
from src.core.config import settings
from src.core.state import app_state

app = FastAPI(
    title=settings.app_name,
    description="Self-healing DevOps agent that watches logs and prepares AI remediation suggestions.",
    version="0.1.0",
)

app.include_router(router)


@app.on_event("startup")
def startup_event() -> None:
    # Start from end to avoid replaying stale logs during demos.
    app_state.watcher.initialize_position(start_from_end=True)

