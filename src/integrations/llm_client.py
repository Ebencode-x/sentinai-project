"""LLM integration scaffold for incident analysis.

Milestone 1: Structured JSON output with Pydantic validation and 3-stage fallback.
Milestone 2: proposed_patch and test_guidance fields added to LLM schema and stub.
"""

from __future__ import annotations

import json
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Literal

import httpx
from pydantic import BaseModel, Field, ValidationError

from src.core.config import settings
from src.models.events import LogIncident, RemediationSuggestion

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JSON schema model — matches what we ask the LLM to return.
# ---------------------------------------------------------------------------


class _LLMJsonResponse(BaseModel):
    """Expected JSON structure from the LLM. All fields required."""

    summary: str = Field(..., min_length=1)
    code_fix: str = Field(..., min_length=1)
    config_change: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    risks: str = Field(..., min_length=1)
    patch_file: str = Field(..., min_length=1)
    proposed_patch: str = Field(..., min_length=1)
    test_guidance: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class BaseLLMClient(ABC):
    """Abstract interface for analyzing incidents with an LLM."""

    @abstractmethod
    def analyze_incident(self, incident: LogIncident) -> RemediationSuggestion:
        """Return a remediation suggestion generated from incident context."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Stub (local, no API key required)
# ---------------------------------------------------------------------------


class StubLLMClient(BaseLLMClient):
    """Safe local placeholder that mimics an AI response.

    Why this exists:
    - Allows end-to-end demos without external API keys.
    - Keeps architecture ready for provider replacement.
    """

    def analyze_incident(self, incident: LogIncident) -> RemediationSuggestion:
        return RemediationSuggestion(
            summary="Potential unhandled exception detected. Add guard clauses and improve error handling.",
            proposed_code_fix=(
                "Wrap failing logic in try/except, validate nullable values before use, "
                "and return controlled HTTP errors instead of raw tracebacks."
            ),
            proposed_config_change=(
                "Set production log level to INFO and route stack traces to secure sink; "
                "consider tuning worker timeout if failures are timeout-related."
            ),
            confidence=0.62,
            risks="Suggestion is heuristic. Validate with tests before rollout.",
            source="stub",
            provider_error=None,
            proposed_patch=(
                "# Before\n"
                "def handle_request(data):\n"
                "    result = process(data)  # may raise\n"
                "    return result\n\n"
                "# After\n"
                "def handle_request(data):\n"
                "    try:\n"
                "        result = process(data)\n"
                "        return result\n"
                "    except Exception as exc:\n"
                "        logger.exception('handle_request failed: %s', exc)\n"
                "        raise HTTPException(status_code=500, detail='Internal error') from exc\n"
            ),
            test_guidance=(
                "1. Mock process() to raise ValueError and assert the endpoint returns HTTP 500.\n"
                "2. Assert the logger.exception call is made with the correct message.\n"
                "3. Verify the response body contains 'Internal error' and not the raw traceback.\n"
                "4. Add a happy-path test confirming valid input still returns the correct result."
            ),
        )


# ---------------------------------------------------------------------------
# OpenAI adapter
# ---------------------------------------------------------------------------


class OpenAILLMClient(BaseLLMClient):
    """OpenAI Chat Completions adapter with structured JSON output."""

    def __init__(self, api_key: str, model: str, timeout_seconds: float) -> None:
        self._api_key = api_key
        self._model = model or "gpt-4o-mini"
        self._timeout_seconds = timeout_seconds

    def analyze_incident(self, incident: LogIncident) -> RemediationSuggestion:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": _incident_prompt(incident)},
            ],
            "temperature": 0.2,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}

        body = _post_json_with_retry(
            url="https://api.openai.com/v1/chat/completions",
            headers=headers,
            json_body=payload,
            timeout_seconds=self._timeout_seconds,
        )

        raw_content = body["choices"][0]["message"]["content"]
        return _parse_llm_output(raw_content, source="provider")


# ---------------------------------------------------------------------------
# Claude adapter
# ---------------------------------------------------------------------------


class ClaudeLLMClient(BaseLLMClient):
    """Anthropic Messages API adapter with structured JSON output."""

    def __init__(self, api_key: str, model: str, timeout_seconds: float) -> None:
        self._api_key = api_key
        self._model = model or "claude-sonnet-4-20250514"
        self._timeout_seconds = timeout_seconds

    def analyze_incident(self, incident: LogIncident) -> RemediationSuggestion:
        payload = {
            "model": self._model,
            "max_tokens": 1200,
            "temperature": 0.2,
            "system": _system_prompt(),
            "messages": [{"role": "user", "content": _incident_prompt(incident)}],
        }
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
        }

        body = _post_json_with_retry(
            url="https://api.anthropic.com/v1/messages",
            headers=headers,
            json_body=payload,
            timeout_seconds=self._timeout_seconds,
        )

        text_chunks = [
            item.get("text", "")
            for item in body.get("content", [])
            if item.get("type") == "text"
        ]
        raw_content = "\n".join(chunk for chunk in text_chunks if chunk.strip())
        return _parse_llm_output(raw_content, source="provider")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_llm_client() -> BaseLLMClient:
    """Choose concrete LLM client by environment configuration."""
    provider = settings.llm_provider.strip().lower()

    if provider == "openai" and settings.llm_api_key:
        return OpenAILLMClient(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    if provider == "claude" and settings.llm_api_key:
        return ClaudeLLMClient(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    return StubLLMClient()


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


def _system_prompt() -> str:
    return (
        "You are a senior SRE and backend engineer. "
        "Analyze runtime failures and provide practical, low-risk remediation guidance. "
        "Always respond with a single raw JSON object — no markdown, no code fences, "
        "no explanation outside the JSON."
    )


def _incident_prompt(incident: LogIncident) -> str:
    from src.core.sanitizer import sanitize_incident_for_prompt

    trigger, stacktrace, context = sanitize_incident_for_prompt(
        incident.trigger_line,
        incident.stacktrace,
        incident.context_before_error,
    )
    lines = [
        "Respond with ONLY a raw JSON object using exactly these keys:",
        "{",
        '  "summary": "one-line description of the failure",',
        '  "code_fix": "description of the code change needed",',
        '  "config_change": "description of any config tuning needed",',
        '  "confidence": 0.0,',
        '  "risks": "what could go wrong applying this fix",',
        '  "patch_file": "repo-relative path of the file to patch e.g. src/services/handler.py",',
        '  "proposed_patch": "unified diff with --- a/file and +++ b/file headers showing the exact change",',
        '  "test_guidance": "numbered list of unit tests to write to validate the patch"',
        "}",
        "",
        "Rules:",
        "- confidence must be a float between 0.0 and 1.0",
        "- proposed_patch MUST be a valid unified diff starting with --- a/<file> and +++ b/<file>",
        "- patch_file MUST be the repo-relative path matching the --- a/<file> header",
        "- test_guidance should be a numbered list of specific test cases",
        "- No markdown, no code fences, no text before or after the JSON",
        '- Escape any double quotes inside string values with \\"',
        "",
        f"Incident ID: {incident.incident_id}",
        f"Severity: {incident.severity}",
        f"Trigger line: {trigger}",
        f"Context before error:\n{context}",
        "",
        f"Stacktrace:\n{stacktrace}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Response parsing — JSON first, section parser fallback, stub last
# ---------------------------------------------------------------------------


def _parse_llm_output(
    text: str,
    *,
    source: Literal["stub", "provider", "fallback"] = "provider",
) -> RemediationSuggestion:
    """Three-stage fallback chain for LLM response parsing.

    Stage 1: Strict JSON parse + Pydantic validation.
    Stage 2: Legacy section-based text parser.
    Stage 3: Stub summary so the API never returns empty.
    """
    suggestion = _try_parse_json(text, source=source)
    if suggestion is not None:
        return suggestion

    logger.warning("JSON parse failed; attempting section parser fallback.")

    suggestion = _try_parse_sections(text, source=source)
    if suggestion is not None:
        return suggestion

    logger.warning("Section parser also failed; using stub summary as last resort.")

    return RemediationSuggestion(
        summary="Could not parse LLM response. Raw output logged for inspection.",
        proposed_code_fix="Review raw LLM output manually.",
        proposed_config_change="No config change derived.",
        confidence=0.1,
        risks="Response parsing failed entirely. Do not act on this suggestion.",
        source="fallback",
        provider_error=f"Unparseable response (first 300 chars): {text[:300]}",
        proposed_patch=None,
        test_guidance=None,
    )


def _strip_fences(text: str) -> str:
    """Remove markdown code fences that models sometimes add despite instructions."""
    fenced = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    fenced = re.sub(r"\s*```$", "", fenced.strip())
    return fenced.strip()


def _try_parse_json(
    text: str,
    *,
    source: Literal["stub", "provider", "fallback"],
) -> RemediationSuggestion | None:
    """Attempt strict JSON parse and Pydantic validation. Returns None on failure."""
    cleaned = _strip_fences(text)

    try:
        raw = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.debug("JSON decode error: %s | raw (first 200): %.200s", exc, cleaned)
        return None

    try:
        validated = _LLMJsonResponse.model_validate(raw)
    except ValidationError as exc:
        logger.debug("Pydantic validation error: %s", exc)
        return None

    return RemediationSuggestion(
        summary=validated.summary,
        proposed_code_fix=validated.code_fix,
        proposed_config_change=validated.config_change,
        confidence=validated.confidence,
        risks=validated.risks,
        source=source,
        provider_error=None,
        patch_file=validated.patch_file,
        proposed_patch=validated.proposed_patch,
        test_guidance=validated.test_guidance,
    )


def _try_parse_sections(
    text: str,
    *,
    source: Literal["stub", "provider", "fallback"],
) -> RemediationSuggestion | None:
    """Legacy section-based parser kept as fallback. Returns None on no match."""
    sections = _extract_sections(text)
    if not sections:
        return None

    confidence_value = 0.5
    raw_confidence = sections.get("CONFIDENCE", "0.5")
    try:
        confidence_value = float(raw_confidence.strip().split()[0])
    except (ValueError, IndexError):
        confidence_value = 0.5

    return RemediationSuggestion(
        summary=sections.get("SUMMARY", "No summary provided."),
        proposed_code_fix=sections.get("CODE_FIX", "No code fix proposed."),
        proposed_config_change=sections.get(
            "CONFIG_CHANGE", "No config change proposed."
        ),
        confidence=max(0.0, min(1.0, confidence_value)),
        risks=sections.get("RISKS", "No risks provided."),
        source=source,
        provider_error=None,
        proposed_patch=sections.get("PROPOSED_PATCH", None),
        test_guidance=sections.get("TEST_GUIDANCE", None),
    )


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------


def _post_json_with_retry(
    *,
    url: str,
    headers: dict[str, str],
    json_body: dict,
    timeout_seconds: float,
) -> dict:
    """POST JSON with exponential backoff on transient failures."""
    max_retries = max(1, settings.llm_max_retries)
    backoff = max(0.1, settings.llm_retry_backoff_seconds)
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.post(url, headers=headers, json=json_body)

            if response.is_success:
                return response.json()

            if _is_retryable_http_status(response.status_code):
                last_error = httpx.HTTPStatusError(
                    f"HTTP {response.status_code}",
                    request=response.request,
                    response=response,
                )
            else:
                response.raise_for_status()
        except (
            httpx.TimeoutException,
            httpx.ConnectError,
            httpx.ReadError,
            httpx.WriteError,
        ) as exc:
            last_error = exc

        if attempt < max_retries - 1:
            sleep_s = backoff * (2**attempt)
            logger.warning(
                "LLM request failed (attempt %s/%s), retrying in %.2fs: %s",
                attempt + 1,
                max_retries,
                sleep_s,
                last_error,
            )
            time.sleep(sleep_s)

    assert last_error is not None
    raise last_error


def _is_retryable_http_status(status_code: int) -> bool:
    if status_code == 429:
        return True
    return status_code in (500, 502, 503, 504)


def _extract_sections(text: str) -> dict[str, str]:
    """Parse SECTION: style text into a dict. Returns empty dict on no match."""
    keys = (
        "SUMMARY",
        "CODE_FIX",
        "CONFIG_CHANGE",
        "CONFIDENCE",
        "RISKS",
        "PROPOSED_PATCH",
        "TEST_GUIDANCE",
    )
    output: dict[str, str] = {}
    current_key = ""
    current_lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        maybe_key = line[:-1] if line.endswith(":") else ""
        if maybe_key in keys:
            if current_key:
                output[current_key] = "\n".join(current_lines).strip()
            current_key = maybe_key
            current_lines = []
            continue
        if current_key:
            current_lines.append(raw_line)

    if current_key:
        output[current_key] = "\n".join(current_lines).strip()

    return output
