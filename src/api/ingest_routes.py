"""Log ingest API: POST /api/ingest.

Lets another service (AgroLink, for example) push error events into the log file
that SentinAI watches. The server writes every line itself, so a client can never
forge log lines, and personal data is masked before anything reaches the disk.
"""

import hmac
import logging
import os
import re
import threading
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, ValidationError

from src.core.rate_limiter import TokenBucket
from src.core.state import app_state

logger = logging.getLogger("sentinai.ingest")

router = APIRouter(prefix="/ingest", tags=["ingest"])

_MIN_KEY_LENGTH = 24
_MAX_BODY_BYTES = 256 * 1024
_MAX_LOG_BYTES = 5 * 1024 * 1024
_MAX_TRACE_LINES = 30  # the watcher closes a block at 40 lines, stay below that
_INGEST_MAX_PER_MINUTE = int(os.getenv("SENTINAI_INGEST_RATE_LIMIT", "30"))

_ingest_limiter = TokenBucket(
    capacity=_INGEST_MAX_PER_MINUTE,
    refill_per_minute=_INGEST_MAX_PER_MINUTE,
)
_write_lock = threading.Lock()
_scan_flag = threading.Lock()  # held while a scan is queued, released when it starts

# Order matters: Bearer is masked before the generic "authorization: ..." rule.
_SCRUBBERS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\[parameters:[^\n]*"), "[parameters: <redacted>]"),
    (re.compile(r"Key \([^)]*\)=\([^)]*\)"), "Key (<redacted>)=(<redacted>)"),
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "<email>"),
    (re.compile(r"(?<!\d)(?:\+?255|0)[67]\d{8}(?!\d)"), "<phone>"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "<ip>"),
    (re.compile(r"(?i)\b(otp|pin)\s*[=:]\s*\d{3,8}\b"), r"\1=<redacted>"),
    (re.compile(r"(?i)\bbearer\s+[\w.~+/=-]+"), "Bearer <redacted>"),
    (
        re.compile(
            r"(?i)\b(password|passwd|secret|token|api[_-]?key|authorization)"
            r"\s*[=:]\s*\S+"
        ),
        r"\1=<redacted>",
    ),
)

# Column-0 trace lines the watcher already understands. Anything else is indented
# so a client can never start a new "ERROR ..." line from inside a traceback.
_TRACE_OK = (
    re.compile(r"^\s"),
    re.compile(r"^Traceback \(most recent call last\):"),
    re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*(Error|Exception):"),
    re.compile(r"^(During handling of the above|The above exception was)"),
)


class IngestEvent(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    traceback: str | None = Field(default=None, max_length=6000)


class IngestBatch(BaseModel):
    source: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,31}$")
    events: list[IngestEvent] = Field(min_length=1, max_length=20)


def scrub(text: str) -> str:
    """Mask personal data and secrets before anything is written."""
    for pattern, replacement in _SCRUBBERS:
        text = pattern.sub(replacement, text)
    return text


def _one_line(text: str) -> str:
    return " ".join(text.split())


def _trace_lines(raw: str) -> list[str]:
    lines: list[str] = []
    for line in scrub(raw).splitlines():
        line = line.rstrip()
        if not line:
            continue
        if not any(pattern.match(line) for pattern in _TRACE_OK):
            line = "  " + line
        lines.append(line)
    if len(lines) > _MAX_TRACE_LINES:
        keep_tail = _MAX_TRACE_LINES - 7
        omitted = len(lines) - (_MAX_TRACE_LINES - 1)
        lines = lines[:6] + [f"  ... {omitted} lines omitted"] + lines[-keep_tail:]
    return lines


def _format_event(source: str, message: str, trace: str | None) -> str:
    # No timestamp here on purpose: the watcher fingerprints the text, and a
    # timestamp would make every event look like a brand new incident.
    lines = [f"ERROR [{source}] {_one_line(scrub(message))}"]
    if trace:
        lines.extend(_trace_lines(trace))
    return "\n".join(lines) + "\n"


def _check_key(provided: str | None) -> None:
    expected = os.getenv("SENTINAI_INGEST_KEY", "")
    if len(expected) < _MIN_KEY_LENGTH:
        raise HTTPException(status_code=503, detail="Ingest is not configured")
    if not provided or not hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid ingest key")


async def _read_body(request: Request) -> bytes:
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > _MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Payload too large")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > _MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="Payload too large")
    return bytes(body)


def _append(path: Path, text: str) -> None:
    with _write_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        size = path.stat().st_size if path.exists() else 0
        # Over the cap: start a fresh file. The watcher resets its own cursor
        # when the file becomes smaller than where it last stopped reading.
        mode = "w" if size + len(text.encode("utf-8")) > _MAX_LOG_BYTES else "a"
        with path.open(mode, encoding="utf-8", newline="\n") as handle:
            handle.write(text)


def _run_scan() -> None:
    # Release first: events that arrive while this scan runs queue the next one.
    _scan_flag.release()
    try:
        app_state.scan_logs_once()
    except Exception:
        logger.exception("Scan after ingest failed")


@router.post("", status_code=202)
async def ingest(
    request: Request,
    background: BackgroundTasks,
    x_ingest_key: Annotated[str | None, Header()] = None,
) -> dict[str, int | str]:
    _check_key(x_ingest_key)
    if not _ingest_limiter.consume():
        raise HTTPException(
            status_code=429,
            detail="Ingest rate limit exceeded",
            headers={"Retry-After": "60"},
        )
    raw = await _read_body(request)
    try:
        batch = IngestBatch.model_validate_json(raw)
    except ValidationError as exc:
        detail = [
            {"loc": [str(part) for part in err["loc"]], "msg": err["msg"]} for err in exc.errors()
        ]
        raise HTTPException(status_code=422, detail=detail) from exc

    text = "".join(
        _format_event(batch.source, event.message, event.traceback) for event in batch.events
    )
    log_path = Path(app_state.watcher.config.log_file_path)
    await run_in_threadpool(_append, log_path, text)

    if _scan_flag.acquire(blocking=False):
        background.add_task(_run_scan)
    return {"accepted": len(batch.events), "source": batch.source}
