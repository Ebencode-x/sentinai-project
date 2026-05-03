"""HTTP routes for health and incident visibility."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.core.state import app_state

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "sentinai"}


@router.get("/stats")
def stats() -> dict:
    return app_state.stats_snapshot()


@router.get("/incidents")
def incidents() -> list[dict]:
    return [incident.model_dump(mode="json") for incident in app_state.recent_incidents]


@router.get("/suggestions")
def suggestions() -> list[dict]:
    return [item.model_dump(mode="json") for item in app_state.recent_suggestions]


@router.get("/suggestions/latest")
def suggestions_latest() -> dict:
    if not app_state.recent_suggestions:
        raise HTTPException(status_code=404, detail="No suggestions yet. Run POST /scan-now after errors appear in logs.")
    return app_state.recent_suggestions[-1].model_dump(mode="json")


@router.post("/scan-now")
def scan_now() -> dict[str, int]:
    count = app_state.scan_logs_once()
    return {"detected_incidents": count}

