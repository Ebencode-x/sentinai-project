"""Secret sanitization for SentinAI.

Prevents secret leakage into LLM prompts, logs, and audit trails
by detecting and redacting credentials before they leave the system.

Defense layers:
    1. Pattern matching  — known secret formats (AWS, GitHub, Stripe, JWT, etc.)
    2. Entropy detection — high-entropy strings flag unknown credentials
    3. Audit trail       — every redaction logged with hash, never plaintext
    4. Protocol          — swappable implementation via SecretSanitizerProtocol

Design principles:
    - Redact, never delete — preserves context while removing sensitive value
    - Fail-safe           — sanitize() never raises; errors produce safe output
    - Immutable results   — SanitizeResult and RedactionRecord are frozen
    - Zero plaintext      — audit records store SHA-256 hash only
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ENTROPY_THRESHOLD = 4.5  # Shannon bits/char — above this is suspicious
_ENTROPY_MIN_LENGTH = 20  # Only check entropy for strings this long
_ENTROPY_MAX_LENGTH = 200  # Ignore extremely long blobs (base64 docs etc.)
_REDACT_LABEL_PREFIX = "REDACTED"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SecretPattern:
    """A named regex pattern that identifies a secret type."""

    name: str  # e.g. "aws-access-key"
    pattern: re.Pattern[str]
    label: str  # e.g. "aws-access-key" used in [REDACTED:aws-access-key]


@dataclass(frozen=True)
class RedactionRecord:
    """Audit record for a single redaction event.

    Stores *no* plaintext — only a SHA-256 hash of the redacted value
    so the audit trail is forensically useful without being a liability.
    """

    pattern_name: str  # which rule triggered (or "entropy" for entropy hits)
    start: int  # character offset in original text
    end: int  # character offset in original text
    value_hash: str  # SHA-256 hex digest of the redacted substring


@dataclass(frozen=True)
class SanitizeResult:
    """Return value of SecretSanitizer.sanitize()."""

    text: str  # cleaned text, safe to log/send
    redactions: tuple[RedactionRecord, ...]  # audit trail (empty if clean)

    @property
    def is_clean(self) -> bool:
        return len(self.redactions) == 0


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class SecretSanitizerProtocol(Protocol):
    """Interface for secret sanitizers — allows swapping implementations."""

    def sanitize(self, text: str) -> SanitizeResult:
        """Return a sanitized copy of *text* and an audit trail."""
        ...


# ---------------------------------------------------------------------------
# Built-in patterns  (ordered — more specific patterns first)
# ---------------------------------------------------------------------------


def _p(name: str, pattern: str, label: str | None = None) -> SecretPattern:
    return SecretPattern(
        name=name,
        pattern=re.compile(pattern),
        label=label or name,
    )


BUILT_IN_PATTERNS: tuple[SecretPattern, ...] = (
    # AWS
    _p("aws-access-key", r"(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![A-Z0-9])"),
    _p("aws-secret-key", r"(?i)aws.{0,20}secret.{0,20}['\"]([0-9a-zA-Z/+]{40})['\"]"),
    # GitHub
    _p("github-token", r"gh[pors]_[A-Za-z0-9]{36,}"),
    # Stripe
    _p("stripe-secret-key", r"sk_live_[A-Za-z0-9]{24,}"),
    _p("stripe-restricted", r"rk_live_[A-Za-z0-9]{24,}"),
    # JWT  (header.payload.signature — all base64url segments)
    _p("jwt-token", r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
    # PEM private keys
    _p("pem-private-key", r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    # Generic API keys in assignments  (api_key = "...", API_KEY: "...")
    _p(
        "generic-api-key",
        r'(?i)(?:api[_-]?key|apikey|api[_-]?secret)\s*[:=]\s*["\']?([A-Za-z0-9_\-]{16,})["\']?',
    ),
    # Passwords embedded in URLs  (scheme://user:password@host)
    _p("url-password", r"(?i)[a-z][a-z0-9+\-.]*://[^:\s/]+:[^@\s/]{6,}@"),
    # Slack tokens
    _p("slack-token", r"xox[baprs]-[0-9A-Za-z\-]{10,}"),
    # Google API keys
    _p("google-api-key", r"AIza[0-9A-Za-z\-_]{35}"),
    # SendGrid
    _p("sendgrid-api-key", r"SG\.[A-Za-z0-9_\-]{22}\.[A-Za-z0-9_\-]{43}"),
    # Twilio
    _p("twilio-account-sid", r"AC[0-9a-fA-F]{32}"),
    _p("twilio-auth-token", r"(?i)twilio.{0,20}auth.{0,20}token.{0,20}[0-9a-fA-F]{32}"),
    # NPM tokens
    _p("npm-token", r"npm_[A-Za-z0-9]{36}"),
    # PyPI tokens
    _p("pypi-token", r"pypi-[A-Za-z0-9_\-]{40,}"),
)


# ---------------------------------------------------------------------------
# Entropy helpers
# ---------------------------------------------------------------------------


def _shannon_entropy(text: str) -> float:
    """Compute Shannon entropy (bits per character) of *text*."""
    if not text:
        return 0.0
    freq = {}
    for ch in text:
        freq[ch] = freq.get(ch, 0) + 1
    length = len(text)
    return -sum((count / length) * math.log2(count / length) for count in freq.values())


def _looks_like_secret(token: str) -> bool:
    """Return True if *token* looks like a high-entropy credential.

    Only checks tokens within the useful length band to avoid false
    positives on long base64 blobs (certificates, embedded files).
    """
    n = len(token)
    if n < _ENTROPY_MIN_LENGTH or n > _ENTROPY_MAX_LENGTH:
        return False
    # Must be mostly alphanumeric/base64 chars — skip prose words
    alnum_ratio = sum(c.isalnum() or c in "+/=_-" for c in token) / n
    if alnum_ratio < 0.85:
        return False
    return _shannon_entropy(token) >= _ENTROPY_THRESHOLD


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _redact_label(label: str) -> str:
    return f"[{_REDACT_LABEL_PREFIX}:{label}]"


# ---------------------------------------------------------------------------
# Core implementation
# ---------------------------------------------------------------------------


class SecretSanitizer:
    """Detect and redact secrets from arbitrary text.

    Usage::

        sanitizer = SecretSanitizer()
        result = sanitizer.sanitize(text)
        safe_text = result.text
        for record in result.redactions:
            logger.warning("Redacted %s at [%d:%d]", record.pattern_name, record.start, record.end)

    Args:
        patterns: Override built-in patterns with a custom sequence.
        entropy_detection: Enable high-entropy token detection (default: True).
    """

    def __init__(
        self,
        patterns: Sequence[SecretPattern] | None = None,
        *,
        entropy_detection: bool = True,
    ) -> None:
        self._patterns = tuple(patterns) if patterns is not None else BUILT_IN_PATTERNS
        self._entropy_detection = entropy_detection

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def sanitize(self, text: str) -> SanitizeResult:
        """Return sanitized *text* and an audit trail of redactions.

        Never raises — malformed input produces a safe fallback.
        """
        try:
            return self._sanitize(text)
        except Exception:  # noqa: BLE001
            # Fail-safe: return a fully redacted placeholder
            return SanitizeResult(
                text="[REDACTED: sanitizer error]",
                redactions=(),
            )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _sanitize(self, text: str) -> SanitizeResult:
        if not text:
            return SanitizeResult(text="", redactions=())

        # Track (start, end, replacement, record) tuples — applied in reverse
        # order so offsets stay valid during substitution.
        hits: list[tuple[int, int, str, RedactionRecord]] = []
        seen_spans: list[tuple[int, int]] = []

        # --- Pass 1: named patterns ---
        for sp in self._patterns:
            for m in sp.pattern.finditer(text):
                start, end = m.start(), m.end()
                if self._overlaps(start, end, seen_spans):
                    continue
                seen_spans.append((start, end))
                replacement = _redact_label(sp.label)
                record = RedactionRecord(
                    pattern_name=sp.name,
                    start=start,
                    end=end,
                    value_hash=_hash(text[start:end]),
                )
                hits.append((start, end, replacement, record))

        # --- Pass 2: entropy detection ---
        if self._entropy_detection:
            for token_match in re.finditer(r"[A-Za-z0-9+/=_\-]{20,200}", text):
                start, end = token_match.start(), token_match.end()
                if self._overlaps(start, end, seen_spans):
                    continue
                token = token_match.group()
                if _looks_like_secret(token):
                    seen_spans.append((start, end))
                    replacement = _redact_label("high-entropy-secret")
                    record = RedactionRecord(
                        pattern_name="entropy",
                        start=start,
                        end=end,
                        value_hash=_hash(token),
                    )
                    hits.append((start, end, replacement, record))

        if not hits:
            return SanitizeResult(text=text, redactions=())

        # Apply substitutions right-to-left to preserve offsets
        hits.sort(key=lambda h: h[0], reverse=True)
        cleaned = text
        for start, end, replacement, _ in hits:
            cleaned = cleaned[:start] + replacement + cleaned[end:]

        # Restore original (left-to-right) order for audit trail
        records = tuple(r for _, _, _, r in sorted(hits, key=lambda h: h[0]))

        return SanitizeResult(text=cleaned, redactions=records)

    @staticmethod
    def _overlaps(start: int, end: int, seen: list[tuple[int, int]]) -> bool:
        return any(s < end and start < e for s, e in seen)
