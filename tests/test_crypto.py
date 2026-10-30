"""Encryption of secrets stored in the database."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from src.core.crypto import KEY_ENV, MASK_MARK, SecretKeyError, decrypt, encrypt, mask_url

URL = "https://hooks.slack.com/services/T000/B000/SECRETVALUE1234"


def test_a_secret_round_trips_and_is_not_readable_in_its_stored_form(secret_key):
    token = encrypt(URL)
    assert token != URL
    assert "SECRETVALUE" not in token
    assert decrypt(token) == URL


def test_a_missing_key_is_reported_with_how_to_fix_it(monkeypatch):
    monkeypatch.delenv(KEY_ENV, raising=False)
    with pytest.raises(SecretKeyError, match=KEY_ENV):
        encrypt(URL)


def test_a_malformed_key_is_rejected(monkeypatch):
    monkeypatch.setenv(KEY_ENV, "not-a-key")
    with pytest.raises(SecretKeyError):
        encrypt(URL)


def test_a_token_made_with_another_key_cannot_be_read(secret_key, monkeypatch):
    token = encrypt(URL)
    monkeypatch.setenv(KEY_ENV, Fernet.generate_key().decode())
    with pytest.raises(SecretKeyError):
        decrypt(token)


def test_a_key_is_rotated_by_putting_the_new_one_first(secret_key, monkeypatch):
    old_token = encrypt(URL)
    new_key = Fernet.generate_key().decode()
    monkeypatch.setenv(KEY_ENV, f"{new_key},{secret_key}")
    assert decrypt(old_token) == URL
    fresh = encrypt(URL)
    monkeypatch.setenv(KEY_ENV, new_key)
    assert decrypt(fresh) == URL


def test_a_masked_url_hides_the_secret_part():
    masked = mask_url(URL)
    assert masked.startswith("https://hooks.slack.com/")
    assert "SECRETVALUE" not in masked
    assert MASK_MARK in masked
    assert masked.endswith(URL[-4:])
