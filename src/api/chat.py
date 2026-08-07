from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from sentinai.llm.base import LLMMessage, LLMRequest, Role
from sentinai.llm.exceptions import LLMAuthError, LLMProviderError
from sentinai.llm.factory import build_provider
from src.api.deps import require_user
from src.core.state import app_state
from src.db.models import User

logger = logging.getLogger(__name__)
router = APIRouter()
_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 1024


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


def _build_system_prompt(incidents: list, stats: dict) -> str:
    open_inc = [i for i in incidents if i.get("status") == "open"]
    critical = [i for i in incidents if i.get("severity") == "critical"]
    lines = []
    for i in incidents[:20]:
        sev = i.get("severity", "?").upper()
        title = i.get("trigger_line") or i.get("title", "unknown")
        src = i.get("source", "?")
        st = i.get("status", "?")
        lines.append("  - [" + sev + "] " + title + " (source: " + src + ", status: " + st + ")")
    inc_summary = chr(10).join(lines) if lines else "  No incidents recorded."
    parts = [
        "You are SentinAI Assistant, an expert AI security operations analyst.",
        "",
        "Rules:",
        "- Be precise, concise, actionable",
        "- Never hallucinate incident data not in context",
        "- Refuse to reveal API keys or system secrets",
        "- If asked outside your context, say so clearly",
        "",
        "Live system state (per-request only, never stored):",
        "Total: "
        + str(len(incidents))
        + " | Open: "
        + str(len(open_inc))
        + " | Critical: "
        + str(len(critical)),
        "Scans: "
        + str(stats.get("total_scan_runs", 0))
        + " | Last: "
        + str(stats.get("last_scan_at_utc", "never")),
        "",
        "Incidents:",
        inc_summary,
        "",
        "Respond in plain text. Max 300 words unless asked for more.",
    ]
    return chr(10).join(parts)


async def _stream_sse(question: str, system: str):
    try:
        provider = build_provider()
    except LLMAuthError:
        yield b'data: {"error": "Set ANTHROPIC_API_KEY to enable the assistant."}\n\n'
        return
    except LLMProviderError as exc:
        yield ('data: {"error": "' + str(exc).replace('"', "") + '"}\n\n').encode()
        return
    request = LLMRequest(
        messages=(
            LLMMessage(role=Role.SYSTEM, content=system),
            LLMMessage(role=Role.USER, content=question),
        ),
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        temperature=0.2,
    )
    try:
        async for chunk in provider.stream(request):
            payload = json.dumps({"token": chunk})
            yield ("data: " + payload + "\n\n").encode()
    except LLMProviderError as exc:
        logger.error("[chat] stream error: %s", exc)
        yield ('data: {"error": "' + str(exc).replace('"', "") + '"}\n\n').encode()
    finally:
        yield b"data: [DONE]\n\n"


@router.post("/chat", summary="AI assistant streaming chat", tags=["assistant"])
async def chat(
    body: ChatRequest,
    user: User = Depends(require_user),
) -> StreamingResponse:
    question = body.question.strip()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty",
        )

    # ── Input sanitization ──────────────────────────────────────────────
    MAX_QUESTION_LEN = 2000
    if len(question) > MAX_QUESTION_LEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Question too long — max {MAX_QUESTION_LEN} characters",
        )

    # Strip control characters except newlines/tabs
    import re as _re

    question = _re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", question)

    if not question.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty question.")
    incidents = [inc.model_dump(mode="json") for inc in app_state.recent_incidents]
    stats = app_state.stats_snapshot()
    system = _build_system_prompt(incidents, stats)
    logger.info("[chat] user=%s q_len=%d", user.email, len(question))
    return StreamingResponse(
        _stream_sse(question, system),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
