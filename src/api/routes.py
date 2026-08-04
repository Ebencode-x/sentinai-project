"""HTTP routes for SentinAI API — Phase 2 + Phase 3 observability."""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel

from src.api.security import require_api_key
from src.core.health import CheckStatus, run_liveness, run_readiness
from src.core.metrics import shared_registry
from src.core.state import app_state

logger = logging.getLogger(__name__)

router = APIRouter()
_PROTECTED = [Depends(require_api_key)]


# ---------------------------------------------------------------------------
# Liveness probe  GET /health/live
# Always returns 200 — Kubernetes restarts pod only if this fails.
# ---------------------------------------------------------------------------


@router.get("/health/live", tags=["observability"])
def health_live() -> dict:
    """Liveness probe — public, no auth required."""
    return run_liveness()


# ---------------------------------------------------------------------------
# Readiness probe  GET /health/ready
# Returns 200 only when all dependency checks pass.
# Returns 503 when any check is FAIL (Kubernetes stops sending traffic).
# ---------------------------------------------------------------------------


@router.get("/health/ready", tags=["observability"])
def health_ready(response: Response) -> dict:
    """Readiness probe — public, no auth required.

    HTTP 200  all checks OK or DEGRADED (service can handle traffic)
    HTTP 503  one or more checks FAIL (service cannot handle traffic)
    """
    report = run_readiness()
    body = report.as_dict()

    if report.status is CheckStatus.FAIL:
        response.status_code = 503

    return body


# ---------------------------------------------------------------------------
# Legacy /health — kept for backward compatibility
# ---------------------------------------------------------------------------


@router.get("/health", tags=["observability"])
def health() -> dict[str, str]:
    """Public health check — backward compatible."""
    return {"status": "ok", "service": "sentinai"}


# ---------------------------------------------------------------------------
# Protected routes
# ---------------------------------------------------------------------------


@router.get("/stats", dependencies=_PROTECTED, tags=["monitoring"])
def stats() -> dict:
    return app_state.stats_snapshot()


@router.get(
    "/metrics",
    response_class=PlainTextResponse,
    dependencies=_PROTECTED,
    tags=["monitoring"],
)
def prometheus_metrics() -> PlainTextResponse:
    """Prometheus text exposition format — scrape with prometheus.yml."""
    return PlainTextResponse(
        content=generate_latest(shared_registry).decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST,
    )


@router.get("/incidents", dependencies=_PROTECTED, tags=["incidents"])
def incidents() -> list[dict]:
    out = []
    for inc in app_state.recent_incidents:
        tl = inc.trigger_line or ""
        if tl.startswith("Traceback"):
            continue
        out.append(
            {
                "id": inc.incident_id,
                "timestamp": inc.detected_at_utc.isoformat(),
                "severity": "critical" if inc.severity == "critical" else "high",
                "title": tl,
                "description": inc.stacktrace or tl,
                "status": "open",
                "source": tl.split(".")[0] if "." in tl else "sentinai",
            }
        )
    return out


@router.get("/suggestions", dependencies=_PROTECTED, tags=["incidents"])
def suggestions() -> list[dict]:
    return [item.model_dump(mode="json") for item in app_state.recent_suggestions]


@router.get("/suggestions/latest", dependencies=_PROTECTED, tags=["incidents"])
def suggestions_latest() -> dict:
    if not app_state.recent_suggestions:
        raise HTTPException(
            status_code=404,
            detail="No suggestions yet. Run POST /scan-now after errors appear in logs.",
        )
    return app_state.recent_suggestions[-1].model_dump(mode="json")


@router.post("/scan-now", dependencies=_PROTECTED, tags=["incidents"])
def scan_now() -> dict[str, int]:
    count = app_state.scan_logs_once()
    return {"detected_incidents": count}


class AutonomyModeUpdate(BaseModel):
    mode: Literal["propose_only", "auto_pr"]


@router.get("/settings/autonomy", dependencies=_PROTECTED, tags=["settings"])
def get_autonomy_mode() -> dict:
    return {"mode": app_state.autonomy_mode}


@router.patch("/settings/autonomy", dependencies=_PROTECTED, tags=["settings"])
def set_autonomy_mode(body: AutonomyModeUpdate) -> dict:
    app_state.set_autonomy_mode(body.mode)
    logger.info("Autonomy mode changed to: %s", body.mode)
    return {"mode": app_state.autonomy_mode}
