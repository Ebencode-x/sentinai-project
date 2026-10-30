"""Encryption for secrets kept in the database, such as notification webhook URLs.

The key comes from SENTINAI_SECRET_KEY. Several keys may be given, separated by
commas: the first one encrypts and every one can decrypt, so a key is rotated by
putting the new key in front of the old one.
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

KEY_ENV = "SENTINAI_SECRET_KEY"
MASK_MARK = "\u2026"
GENERATE_HINT = (
    'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
)


class SecretKeyError(RuntimeError):
    """The key is missing or malformed, or it cannot decrypt a stored secret."""


def _cipher() -> MultiFernet:
    raw = os.getenv(KEY_ENV, "")
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    if not parts:
        raise SecretKeyError(f"{KEY_ENV} is not set. Generate one with: {GENERATE_HINT}")
    try:
        return MultiFernet([Fernet(part.encode("ascii")) for part in parts])
    except (ValueError, UnicodeEncodeError) as exc:
        raise SecretKeyError(f"{KEY_ENV} is not a valid Fernet key.") from exc


def encrypt(text: str) -> str:
    return _cipher().encrypt(text.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    try:
        return _cipher().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise SecretKeyError("A stored secret cannot be decrypted with the current key.") from exc


def mask_url(url: str) -> str:
    """Show where a URL points without revealing its secret path or token."""
    parts = urlsplit(url)
    tail = url[-4:] if len(url) > 16 else ""
    if parts.scheme and parts.netloc:
        return f"{parts.scheme}://{parts.netloc}/{MASK_MARK}{tail}"
    return f"{MASK_MARK}{tail}"
