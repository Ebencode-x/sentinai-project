"""LLM integration scaffold for incident analysis.

This module intentionally contains a provider-agnostic interface and a
placeholder implementation. Swap `StubLLMClient` with concrete providers
(OpenAI, Anthropic, etc.) in production.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx

from src.core.config import settings
from src.models.events import LogIncident, RemediationSuggestion


class BaseLLMClient(ABC):
    """Abstract interface for analyzing incidents with an LLM."""

    @abstractmethod
    def analyze_incident(self, incident: LogIncident) -> RemediationSuggestion:
        """Return a remediation suggestion generated from incident context."""
        raise NotImplementedError


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
        )


class OpenAILLMClient(BaseLLMClient):
    """Simple OpenAI Chat Completions adapter.

    This implementation is intentionally minimal and API-key based.
    It extracts plain text from the response and maps it to our model.
    """

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

        with httpx.Client(timeout=self._timeout_seconds) as client:
            response = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            body = response.json()

        content = body["choices"][0]["message"]["content"]
        return _parse_text_response(content)


class ClaudeLLMClient(BaseLLMClient):
    """Simple Anthropic Messages API adapter."""

    def __init__(self, api_key: str, model: str, timeout_seconds: float) -> None:
        self._api_key = api_key
        self._model = model or "claude-3-5-sonnet-latest"
        self._timeout_seconds = timeout_seconds

    def analyze_incident(self, incident: LogIncident) -> RemediationSuggestion:
        payload = {
            "model": self._model,
            "max_tokens": 900,
            "temperature": 0.2,
            "system": _system_prompt(),
            "messages": [{"role": "user", "content": _incident_prompt(incident)}],
        }
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
        }

        with httpx.Client(timeout=self._timeout_seconds) as client:
            response = client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            body = response.json()

        text_chunks = [item.get("text", "") for item in body.get("content", []) if item.get("type") == "text"]
        content = "\n".join(chunk for chunk in text_chunks if chunk.strip())
        return _parse_text_response(content)


def build_llm_client() -> BaseLLMClient:
    """Factory: choose concrete LLM client by environment configuration.

    Falls back to `StubLLMClient` to keep local demos resilient even when
    provider keys are missing or intentionally disabled.
    """
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


def _system_prompt() -> str:
    return (
        "You are a senior SRE and backend engineer. "
        "Analyze runtime failures and provide practical, low-risk remediation guidance."
    )


def _incident_prompt(incident: LogIncident) -> str:
    return (
        "Return five sections exactly in this format:\n"
        "SUMMARY:\n"
        "CODE_FIX:\n"
        "CONFIG_CHANGE:\n"
        "CONFIDENCE:\n"
        "RISKS:\n\n"
        f"Incident ID: {incident.incident_id}\n"
        f"Severity: {incident.severity}\n"
        f"Trigger line: {incident.trigger_line}\n"
        f"Context before error:\n{incident.context_before_error}\n\n"
        f"Stacktrace:\n{incident.stacktrace}\n"
    )


def _parse_text_response(text: str) -> RemediationSuggestion:
    """Best-effort parser for simple sectioned LLM outputs."""
    sections = _extract_sections(text)

    confidence_value = 0.5
    raw_confidence = sections.get("CONFIDENCE", "0.5")
    try:
        confidence_value = float(raw_confidence.strip().split()[0])
    except (ValueError, IndexError):
        confidence_value = 0.5

    return RemediationSuggestion(
        summary=sections.get("SUMMARY", "No summary provided."),
        proposed_code_fix=sections.get("CODE_FIX", "No code fix proposed."),
        proposed_config_change=sections.get("CONFIG_CHANGE", "No config change proposed."),
        confidence=max(0.0, min(1.0, confidence_value)),
        risks=sections.get("RISKS", "No risks provided."),
    )


def _extract_sections(text: str) -> dict[str, str]:
    keys = ("SUMMARY", "CODE_FIX", "CONFIG_CHANGE", "CONFIDENCE", "RISKS")
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
    if not output:
        output["SUMMARY"] = text.strip() or "Empty response."
    return output

