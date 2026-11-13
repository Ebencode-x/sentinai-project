"""Tests for the extra named secret patterns (key formats used in this project)."""

import pytest

from src.services.secret_sanitizer import SecretSanitizer

TAIL = "Zx9Yw8Vu7Ts6Rq5Po4Nm3Lk2Ji1Hg0Fe9Dc8Ba7"
PAT_TAIL = "11ABCDEFG0abcdefghijkl_mnopqrstuvwxyz0123456789ABCDEFGH"

CASES = [
    ("sentinai-key", "snl_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6"),
    ("anthropic-key", "sk-ant-api03-" + TAIL),
    ("openai-key", "sk-proj-" + TAIL),
    ("github-pat", "github_pat_" + PAT_TAIL),
    ("bearer-token", "Bearer " + "abcDEF123456ghiJKL789mnoPQR012stuVWX"),
]

PLAIN = [
    "ValueError: invalid literal for int() at line 42",
    "task-queue-worker-process-handler-retry-count-exceeded",
    "disk-backed-storage-volume-name-for-the-cache-layer-v2",
    "Bearer of bad news, said the operator",
]


@pytest.mark.parametrize(("name", "secret"), CASES)
def test_named_pattern_catches_secret(name, secret):
    sanitizer = SecretSanitizer(entropy_detection=False)
    result = sanitizer.sanitize(f"auth failed for {secret} on retry")
    assert secret not in result.text
    assert name in {r.pattern_name for r in result.redactions}


@pytest.mark.parametrize("secret", [c[1] for c in CASES])
def test_sanitizing_twice_changes_nothing(secret):
    sanitizer = SecretSanitizer()
    once = sanitizer.sanitize(f"auth failed for {secret} on retry")
    twice = sanitizer.sanitize(once.text)
    assert twice.text == once.text
    assert not twice.redactions


@pytest.mark.parametrize("text", PLAIN)
def test_plain_text_is_left_alone(text):
    result = SecretSanitizer(entropy_detection=False).sanitize(text)
    assert result.text == text
    assert not result.redactions
