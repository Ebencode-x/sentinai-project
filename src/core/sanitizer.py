"""Input sanitization utilities for SentinAI.

Prevents prompt injection attacks by cleaning incident data
before it is embedded in LLM prompts.
"""

from __future__ import annotations

import re

_MAX_STACKTRACE_CHARS = 3000
_MAX_TRIGGER_CHARS = 400

_INJECTION_PATTERNS = re.compile(
    r"(ignore\s+(all\s+)?previous\s+instructions?|"
    r"you\s+are\s+now|"
    r"new\s+instructions?:|"
    r"system\s*:|"
    r"<\s*/?(?:system|user|assistant)\s*>|"
    r"\n\s*###)",
    re.IGNORECASE,
)


def sanitize_for_prompt(text: str, max_chars: int) -> str:
    """Truncate and strip prompt-injection patterns from incident text.

    Args:
        text: Raw text from log file (stacktrace or trigger line).
        max_chars: Hard character limit before LLM submission.

    Returns:
        Cleaned, truncated string safe to embed in an LLM prompt.
    """
    cleaned = _INJECTION_PATTERNS.sub("[REDACTED]", text)
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars] + f"\n... [truncated at {max_chars} chars]"
    return cleaned


def sanitize_incident_for_prompt(
    trigger_line: str,
    stacktrace: str,
    context_before_error: str,
) -> tuple[str, str, str]:
    """Sanitize all three incident text fields for LLM submission."""
    return (
        sanitize_for_prompt(trigger_line, _MAX_TRIGGER_CHARS),
        sanitize_for_prompt(stacktrace, _MAX_STACKTRACE_CHARS),
        sanitize_for_prompt(context_before_error, 500),
    )
