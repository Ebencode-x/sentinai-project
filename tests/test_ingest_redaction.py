"""Ingest masks named secrets before the fingerprint is computed."""

from datetime import UTC, datetime

from src.api.event_routes import EventIn, _prepare
from src.services.incident_redaction import redact_known_secrets

KEY_A = "snl_" + "a1B2c3D4" * 5
KEY_B = "snl_" + "Z9y8X7w6" * 5
BEARER_TOKEN = "abcDEF123456abcDEF123456abcDEF"


def _event(message, stacktrace=None, exception_type=None):
    return EventIn.model_construct(
        event_id="e1",
        timestamp=None,
        level="error",
        message=message,
        exception_type=exception_type,
        stacktrace=stacktrace,
        environment=None,
        release=None,
        request_id=None,
    )


def _prep(message, stacktrace=None, exception_type=None):
    return _prepare("agrolink", _event(message, stacktrace, exception_type), datetime.now(UTC))


def test_secrets_are_masked_in_message_and_stacktrace():
    prepared = _prep(
        f"boot failed key={KEY_A}",
        stacktrace=f"Traceback\n  Authorization: Bearer {BEARER_TOKEN}",
    )
    assert KEY_A not in prepared.message
    assert BEARER_TOKEN not in (prepared.stacktrace or "")


def test_two_different_keys_give_the_same_fingerprint():
    first = _prep(f"boot failed key={KEY_A}")
    second = _prep(f"boot failed key={KEY_B}")
    assert first.fingerprint == second.fingerprint


def test_a_different_sentence_gives_a_different_fingerprint():
    first = _prep(f"boot failed key={KEY_A}")
    other = _prep(f"payment failed key={KEY_A}")
    assert first.fingerprint != other.fingerprint


def test_plain_messages_are_not_changed():
    prepared = _prep("disk is full on volume data")
    assert prepared.message == "disk is full on volume data"


def test_entropy_is_off_for_ingest_so_hashes_survive():
    text = "trace 9f2c4e7a1b3d5f60718293a4b5c6d7e8f9012345"
    assert redact_known_secrets(text) == text
