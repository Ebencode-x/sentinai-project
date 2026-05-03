"""HTTP routes for health and incident visibility."""

from __future__ import annotations

from fastapi import APIRouter

from src.core.state import app_state

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "sentinai"}


@router.get("/incidents")
def incidents() -> list[dict]:
    return [incident.model_dump(mode="json") for incident in app_state.recent_incidents]


@router.post("/scan-now")
def scan_now() -> dict[str, int]:
    count = app_state.scan_logs_once()
    return {"detected_incidents": count}

