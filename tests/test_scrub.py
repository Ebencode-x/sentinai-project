"""Tests for the masking rules in src/core/scrub.py."""

import pytest

from src.core.scrub import scrub


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("user a@b.com failed", "user <email> failed"),
        ("call 0712345678 now", "call <phone> now"),
        ("call +255712345678 now", "call <phone> now"),
        ("from 10.0.0.1 failed", "from <ip> failed"),
        ("otp: 123456", "otp=<redacted>"),
        ("got Bearer abc.def-123 here", "got Bearer <redacted> here"),
        ("password=hunter2", "password=<redacted>"),
        (
            "Key (email)=(a@b.com) already exists.",
            "Key (<redacted>)=(<redacted>) already exists.",
        ),
        ("[parameters: ('a@b.com', 'Juma')]", "[parameters: <redacted>]"),
        ("KeyError: 'customer_id'", "KeyError: 'customer_id'"),
    ],
)
def test_scrub_masks_personal_data(raw, expected):
    assert scrub(raw) == expected


def test_scrub_masks_every_occurrence():
    assert scrub("a@b.com and c@d.com") == "<email> and <email>"
