"""Input sanitization utilities for SentinAI.

Prevents prompt injection attacks by cleaning incident data
before it is embedded in LLM prompts.

Defense layers:
    1. Pattern matching  — known injection phrases (regex)
    2. Repetition attack — repeated tokens flooding the prompt
    3. Entropy check     — low character diversity signals obfuscated payloads
    4. Hard truncation   — enforces max_chars before LLM submission
"""

from __future__ import annotations

import re

_MAX_STACKTRACE_CHARS = 3000
_MAX_TRIGGER_CHARS = 400
_MAX_CONTEXT_CHARS = 500

# Minimum unique characters required — low diversity signals garbage/attack input
_MIN_UNIQUE_CHARS = 10

# If any single token repeats more than this fraction of total tokens, flag it
_REPETITION_THRESHOLD = 0.4

_INJECTION_PATTERNS = re.compile(
    r"(ignore\s+(all\s+)?previous\s+instructions?|"
    r"you\s+are\s+now|"
    r"new\s+instructions?:|"
    r"system\s*:|"
    r"<\s*/?(?:system|user|assistant)\s*>|"
    r"\n\s*###)",
    re.IGNORECASE,
)


def _is_low_entropy(text: str) -> bool:
    """Return True if text has suspiciously low character diversity.

    Detects obfuscated payloads like "aaaaaaa..." or single-char floods.
    Only applied to non-trivial length inputs to avoid false positives.
    """
    if len(text) < 20:
        return False
    return len(set(text)) < _MIN_UNIQUE_CHARS


def _is_repetition_attack(text: str) -> bool:
    """Return True if a single token dominates the input.

    Detects attacks like "ignore ignore ignore ignore ..." that try to
    overwhelm the prompt context with a repeated instruction fragment.
    Only applied when there are enough tokens to form a pattern.
    """
    tokens = text.split()
    if len(tokens) < 8:
        return False
    most_common_count = max(tokens.count(t) for t in set(tokens))
    return (most_common_count / len(tokens)) > _REPETITION_THRESHOLD


def sanitize_for_prompt(text: str, max_chars: int) -> str:
    """Truncate and strip prompt-injection patterns from incident text.

    Applies three defense layers in order:
        1. Low-entropy detection (character diversity)
        2. Repetition attack detection (token frequency)
        3. Known injection pattern matching (regex)
        4. Hard truncation at max_chars

    Args:
        text: Raw text from log file (stacktrace or trigger line).
        max_chars: Hard character limit before LLM submission.

    Returns:
        Cleaned, truncated string safe to embed in an LLM prompt.
    """
    if _is_low_entropy(text):
        return "[REDACTED: low-entropy input]"

    if _is_repetition_attack(text):
        return "[REDACTED: repetition attack detected]"

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
        sanitize_for_prompt(context_before_error, _MAX_CONTEXT_CHARS),
    )
