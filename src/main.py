"""FastAPI entrypoint for SentinAI."""

# Load `.env` from project root before any settings import (Git Bash / local runs).
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.chat import router as chat_router
from src.api.routes import router
from src.core.config import settings
from src.core.state import app_state

_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start from end to avoid replaying stale logs during demos.
    app_state.watcher.initialize_position(start_from_end=True)
    app_state.load_incidents()
    yield


app = FastAPI(
    title=settings.app_name,
    description=(
        "Self-healing DevOps agent that watches logs and prepares AI remediation suggestions."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — origins controlled via SENTINAI_CORS_ORIGINS env var
# Dev default: http://localhost:5173 (Vite dev server)
# Production: set to your frontend domain, e.g. https://app.sentinai.io
# Never use ["*"] in production — API keys would be exposed cross-origin.
# ---------------------------------------------------------------------------
_raw_origins = settings.cors_origins if hasattr(settings, "cors_origins") else ""
_origins: list[str] = (
    [o.strip() for o in _raw_origins.split(",") if o.strip()]
    if _raw_origins
    else ["http://localhost:5173", "http://127.0.0.1:5173"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type", "Accept"],
    max_age=600,  # preflight cache: 10 minutes
)

app.include_router(router)
app.include_router(chat_router)
