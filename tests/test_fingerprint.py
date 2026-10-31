"""Fingerprints: the same crash groups together, different crashes and services do not."""

from __future__ import annotations

from src.core.fingerprint import exception_type_of, fingerprint, normalize, top_frames

TRACE = """Traceback (most recent call last):
  File "/srv/app/orders/api.py", line 40, in handle
    return create(order)
  File "/srv/app/orders/service.py", line 88, in create
    customer = order["customer_id"]
KeyError: 'customer_id'
"""


def test_ids_hashes_and_numbers_are_replaced():
    text = "id 7f3a9c1e-1111-2222-3333-444455556666 took 52 ms at 0xdeadbeef"
    assert normalize(text) == "id # took # ms at #"


def test_the_same_crash_with_different_numbers_has_one_fingerprint():
    first = fingerprint("agrolink", "Order 123 not found")
    second = fingerprint("agrolink", "Order 456 not found")
    assert first == second
    assert len(first) == 16


def test_line_numbers_do_not_change_the_fingerprint():
    moved = TRACE.replace("line 40", "line 41").replace("line 88", "line 90")
    assert fingerprint("agrolink", "boom", None, TRACE) == fingerprint(
        "agrolink", "boom", None, moved
    )


def test_two_services_never_share_a_fingerprint():
    assert fingerprint("agrolink", "boom") != fingerprint("orders-api", "boom")


def test_a_different_message_or_exception_gives_a_different_fingerprint():
    assert fingerprint("agrolink", "Customer missing") != fingerprint("agrolink", "Order missing")
    assert fingerprint("agrolink", "boom", "KeyError") != fingerprint("agrolink", "boom", "OSError")


def test_the_exception_type_is_read_from_the_stacktrace_when_not_given():
    assert exception_type_of(None, TRACE) == "KeyError"
    assert exception_type_of("ValueError", TRACE) == "ValueError"
    assert exception_type_of(None, None) == ""


def test_only_the_innermost_frames_are_used_and_paths_are_shortened():
    assert top_frames(TRACE) == ["orders/api.py:handle", "orders/service.py:create"]
    assert top_frames(TRACE, count=1) == ["orders/service.py:create"]
    windows = r'File "C:\app\orders\service.py", line 3, in create'
    assert top_frames(windows) == ["orders/service.py:create"]
    assert top_frames(None) == []
