"""Mask personal data and secrets in text that came from another service.

Used by the event ingest before anything is stored. The rules cover database
error details, emails, Tanzanian phone numbers, IP addresses, OTPs and PINs,
bearer tokens and common secret names.
"""

import re

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


def scrub(text: str) -> str:
    """Mask personal data and secrets before anything is stored."""
    for pattern, replacement in _SCRUBBERS:
        text = pattern.sub(replacement, text)
    return text
