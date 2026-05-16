"""Phase 3 — Structured JSON logging.

Replaces plain-text log lines with machine-readable JSON records that
can be ingested by Grafana Loki, Datadog, ELK, or any log aggregator.

Record schema (every field always present)
------------------------------------------
{
    "timestamp":  "2026-05-16T10:00:00.123456Z",   # ISO-8601 UTC
    "level":      "INFO",
    "logger":     "src.services.pipeline",
    "message":    "Stage 0: sanitizing incident input",
    "request_id": "req-abc123",                     # or "none"
    "tenant":     "acme-corp",                      # or "anonymous"
    "service":    "sentinai",
    "version":    "1.0.0",
    "exc_info":   null | "Traceback ..."
}

Usage
-----
Call ``configure_logging()`` once at application startup (e.g. in main.py).
Use ``bind_request_context()`` in middleware to attach request_id / tenant
to every log line within a request's lifetime.

    from src.core.structured_logging import configure_logging, bind_request_context

    configure_logging(level="INFO", fmt="json")   # fmt="text" for local dev

    # Inside FastAPI middleware:
    with bind_request_context(request_id="req-xyz", tenant="acme"):
        ...

Thread / async safety
---------------------
Context is stored in a ``contextvars.ContextVar`` — isolated per async
task and per thread, so concurrent requests never bleed context.
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

# ---------------------------------------------------------------------------
# Context variables (per-request, per-task)
# ---------------------------------------------------------------------------

_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="none")
_tenant_var: contextvars.ContextVar[str] = contextvars.ContextVar("tenant", default="anonymous")

_SERVICE_NAME = "sentinai"
_SERVICE_VERSION = "1.0.0"


def set_request_context(*, request_id: str, tenant: str = "anonymous") -> None:
    """Set request-scoped context for the current async task / thread."""
    _request_id_var.set(request_id)
    _tenant_var.set(tenant)


def clear_request_context() -> None:
    """Reset context to defaults (call at end of request)."""
    _request_id_var.set("none")
    _tenant_var.set("anonymous")


def get_request_id() -> str:
    return _request_id_var.get()


def get_tenant() -> str:
    return _tenant_var.get()


class bind_request_context:  # noqa: N801  (context manager — lowercase is idiomatic)
    """Context manager that sets and clears request context automatically.

    Example::

        with bind_request_context(request_id="req-123", tenant="acme"):
            do_work()
        # context is restored to previous values here
    """

    def __init__(self, *, request_id: str, tenant: str = "anonymous") -> None:
        self._request_id = request_id
        self._tenant = tenant
        self._tokens: list = []

    def __enter__(self) -> bind_request_context:
        self._tokens.append(_request_id_var.set(self._request_id))
        self._tokens.append(_tenant_var.set(self._tenant))
        return self

    def __exit__(self, *_: object) -> None:
        for token in reversed(self._tokens):
            token.var.reset(token)
        self._tokens.clear()


# ---------------------------------------------------------------------------
# JSON formatter
# ---------------------------------------------------------------------------


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        body: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": _request_id_var.get(),
            "tenant": _tenant_var.get(),
            "service": _SERVICE_NAME,
            "version": _SERVICE_VERSION,
        }

        if record.exc_info:
            body["exc_info"] = self.formatException(record.exc_info)
        else:
            body["exc_info"] = None

        # Attach any extra fields passed via logger.info("msg", extra={...})
        _STANDARD_ATTRS = {
            "args",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "message",
            "module",
            "msecs",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "thread",
            "threadName",
            "taskName",
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                body[key] = value

        return json.dumps(body, default=str)


# ---------------------------------------------------------------------------
# Text formatter (human-readable for local dev)
# ---------------------------------------------------------------------------


class _TextFormatter(logging.Formatter):
    """Coloured plain-text formatter for local development."""

    _COLOURS = {
        "DEBUG": "\033[36m",  # cyan
        "INFO": "\033[32m",  # green
        "WARNING": "\033[33m",  # yellow
        "ERROR": "\033[31m",  # red
        "CRITICAL": "\033[35m",  # magenta
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        colour = self._COLOURS.get(record.levelname, "")
        reset = self._RESET
        ts = datetime.fromtimestamp(record.created, tz=UTC).strftime("%H:%M:%S.%f")[:-3]
        rid = _request_id_var.get()
        tenant = _tenant_var.get()
        prefix = f"{ts} {colour}{record.levelname:8}{reset} [{record.name}]"
        ctx = f" rid={rid} tenant={tenant}" if rid != "none" else ""
        line = f"{prefix}{ctx} {record.getMessage()}"
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


# ---------------------------------------------------------------------------
# Public configuration entry point
# ---------------------------------------------------------------------------


def configure_logging(
    level: str = "INFO",
    fmt: str = "json",
    stream: Any = None,
) -> None:
    """Configure the root logger with structured (JSON) or text output.

    Parameters
    ----------
    level:
        Logging level name: "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL".
    fmt:
        ``"json"`` for production (default), ``"text"`` for local dev.
    stream:
        Output stream.  Defaults to ``sys.stdout``.
    """
    if stream is None:
        stream = sys.stdout

    formatter: logging.Formatter
    if fmt == "json":
        formatter = _JsonFormatter()
    else:
        formatter = _TextFormatter()

    handler = logging.StreamHandler(stream)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove any existing handlers to avoid duplicate output
    root.handlers.clear()
    root.addHandler(handler)

    # Silence noisy third-party loggers
    for noisy in ("httpx", "httpcore", "urllib3", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
