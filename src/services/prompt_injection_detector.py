"""D3 — Prompt Injection Detector.

Scans free-text fields for prompt-injection attempts before they reach
the LLM.  Returns a lightweight result object so callers can decide
whether to block or just flag.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------

# Each tuple: (pattern, human-readable label)
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Classic instruction override
    (
        re.compile(
            r"ignore\s+(all\s+)?(previous|prior|above)"
            r"\s+(prompt|instruction|context|text)s?",
            re.I,
        ),
        "instruction-override",
    ),
    (
        re.compile(
            r"disregard\s+(all\s+)?(previous|prior|above)"
            r"\s+(prompt|instruction|context|text)s?",
            re.I,
        ),
        "instruction-override",
    ),
    (
        re.compile(r"forget\s+(everything|all)\s+(you|i|we)\s+(know|said|told)", re.I),
        "instruction-override",
    ),
    # Persona hijack
    (re.compile(r"you\s+are\s+now\b", re.I), "persona-hijack"),
    (re.compile(r"\bact\s+as\b", re.I), "persona-hijack"),
    (re.compile(r"\bpretend\s+(you\s+are|to\s+be)\b", re.I), "persona-hijack"),
    (re.compile(r"\brole\s*[-:]?\s*play\b", re.I), "persona-hijack"),
    (re.compile(r"\byour\s+new\s+(role|persona|identity|name)\b", re.I), "persona-hijack"),
    # Jailbreak keywords
    (re.compile(r"\bDAN\b"), "jailbreak"),
    (re.compile(r"developer\s+mode", re.I), "jailbreak"),
    (re.compile(r"jailbreak", re.I), "jailbreak"),
    (re.compile(r"do\s+anything\s+now", re.I), "jailbreak"),
    (re.compile(r"no\s+restrictions", re.I), "jailbreak"),
    (re.compile(r"without\s+(any\s+)?restrictions", re.I), "jailbreak"),
    # Prompt format leakage (template tokens from various LLM formats)
    (re.compile(r"<\|system\|>", re.I), "prompt-format-leak"),
    (re.compile(r"<\|user\|>", re.I), "prompt-format-leak"),
    (re.compile(r"<\|assistant\|>", re.I), "prompt-format-leak"),
    (re.compile(r"\[INST\]", re.I), "prompt-format-leak"),
    (re.compile(r"\[/INST\]", re.I), "prompt-format-leak"),
    (re.compile(r"###\s*(Human|Assistant|System)\s*:", re.I), "prompt-format-leak"),
    (re.compile(r"<s>|</s>"), "prompt-format-leak"),
    (re.compile(r"<<SYS>>|<</SYS>>"), "prompt-format-leak"),
    # Data exfiltration hints
    (
        re.compile(
            r"(print|output|reveal|show|display|return|leak)\s+(your\s+)?"
            r"(system\s+)?(prompt|instruction|context|secret|key|token|password)",
            re.I,
        ),
        "exfiltration",
    ),
    (
        re.compile(r"what\s+(is|are)\s+your\s+(instruction|prompt|system|rule)s?", re.I),
        "exfiltration",
    ),
    (
        re.compile(r"repeat\s+(everything|all)\s+(above|before|prior)", re.I),
        "exfiltration",
    ),
    # Indirect injection markers
    (re.compile(r"\{\{.*?\}\}", re.S), "template-injection"),
    (re.compile(r"\[\[.*?\]\]", re.S), "template-injection"),
]

# Heuristic: suspiciously long single token (no spaces) — obfuscation attempt
_MAX_TOKEN_LENGTH = 200


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class InjectionDetectionResult:
    """Result of a prompt injection scan."""

    is_injection: bool
    detections: list[dict[str, str]] = field(default_factory=list)
    # Which field triggered first (for audit)
    flagged_field: str | None = None

    @property
    def labels(self) -> list[str]:
        return [d["label"] for d in self.detections]

    def __bool__(self) -> bool:
        return self.is_injection


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


class PromptInjectionDetector:
    """Stateless detector — safe to share across threads."""

    def scan(self, text: str, field_name: str = "unknown") -> InjectionDetectionResult:
        """Scan a single text field.

        Returns an :class:`InjectionDetectionResult` describing every
        detection hit found (all patterns are checked, not just the first).
        """
        detections: list[dict[str, str]] = []

        for pattern, label in _PATTERNS:
            for match in pattern.finditer(text):
                detections.append(
                    {
                        "label": label,
                        "matched": match.group(0)[:120],  # truncate for safety
                        "field": field_name,
                    }
                )

        # Heuristic: token length
        for token in text.split():
            if len(token) > _MAX_TOKEN_LENGTH:
                detections.append(
                    {
                        "label": "long-token-obfuscation",
                        "matched": token[:120],
                        "field": field_name,
                    }
                )

        return InjectionDetectionResult(
            is_injection=bool(detections),
            detections=detections,
            flagged_field=field_name if detections else None,
        )

    def scan_fields(self, fields: dict[str, str]) -> InjectionDetectionResult:
        """Scan multiple named fields.

        All fields are scanned; detections from all are merged.
        The :attr:`flagged_field` is set to the first field that triggered.
        """
        all_detections: list[dict[str, str]] = []
        first_flagged: str | None = None

        for field_name, text in fields.items():
            if not text:
                continue
            result = self.scan(text, field_name=field_name)
            if result.is_injection:
                if first_flagged is None:
                    first_flagged = field_name
                all_detections.extend(result.detections)

        return InjectionDetectionResult(
            is_injection=bool(all_detections),
            detections=all_detections,
            flagged_field=first_flagged,
        )


# Module-level singleton
_detector = PromptInjectionDetector()


def scan_incident_fields(fields: dict[str, str]) -> InjectionDetectionResult:
    """Convenience wrapper around the module singleton."""
    return _detector.scan_fields(fields)
