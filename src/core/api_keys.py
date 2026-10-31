"""API keys for event sources.

A key looks like snl_<8 hex>_<43 url-safe characters>. The first two parts are a
public prefix used to find the source. Only a SHA-256 hash of the whole key is
stored. That is enough because the secret part is random and long, so there is
nothing to brute-force, unlike a human password.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets

KEY_PATTERN = re.compile(r"^(snl_[0-9a-f]{8})_[A-Za-z0-9_-]{43}$")


def generate_key() -> tuple[str, str, str]:
    """Return (full key, public prefix, hash). The full key is shown once, never stored."""
    prefix = "snl_" + secrets.token_hex(4)
    key = f"{prefix}_{secrets.token_urlsafe(32)}"
    return key, prefix, hash_key(key)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def prefix_of(key: str | None) -> str | None:
    """The public prefix of a well-formed key, or None for anything else."""
    match = KEY_PATTERN.match(key or "")
    return match.group(1) if match else None


def matches(key: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_key(key), stored_hash)
