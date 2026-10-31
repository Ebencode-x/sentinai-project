"""Fingerprints for events from sources.

The same crash in the same service must give the same fingerprint, whatever the
ids, numbers and line numbers in it. Different services never share one.
"""

from __future__ import annotations

import hashlib
import re

FRAMES_USED = 3

_VOLATILE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
    r"|0x[0-9a-fA-F]+"
    r"|\b[0-9a-fA-F]{8,}\b"
    r"|\d+"
)
_FRAME = re.compile(r'File "([^"]+)", line \d+, in (\S+)')
_EXCEPTION_LINE = re.compile(
    r"^([A-Za-z_][\w.]*(?:Error|Exception|Warning|Exit|Interrupt))\b", re.MULTILINE
)


def normalize(text: str) -> str:
    """One line, with ids, hashes and numbers replaced by a placeholder."""
    return _VOLATILE.sub("#", " ".join(text.split()))


def exception_type_of(exception_type: str | None, stacktrace: str | None) -> str:
    if exception_type and exception_type.strip():
        return exception_type.strip()
    if stacktrace:
        found = _EXCEPTION_LINE.findall(stacktrace)
        if found:
            return found[-1]
    return ""


def top_frames(stacktrace: str | None, count: int = FRAMES_USED) -> list[str]:
    """The innermost frames as 'folder/file.py:function', without line numbers."""
    if not stacktrace:
        return []
    frames = []
    for path, function in _FRAME.findall(stacktrace):
        parts = [part for part in path.replace("\\", "/").split("/") if part]
        frames.append(f"{'/'.join(parts[-2:])}:{function}")
    return frames[-count:]


def fingerprint(
    source: str,
    message: str,
    exception_type: str | None = None,
    stacktrace: str | None = None,
) -> str:
    parts = [
        source,
        exception_type_of(exception_type, stacktrace),
        normalize(message),
        *top_frames(stacktrace),
    ]
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:16]
