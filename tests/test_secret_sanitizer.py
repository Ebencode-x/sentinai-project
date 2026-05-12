"""Tests for src/services/secret_sanitizer.py — B4 secret leakage prevention.

Coverage:
    - All built-in patterns (AWS, GitHub, Stripe, JWT, PEM, generic, URL, etc.)
    - Entropy detection (high-entropy token flagging)
    - Audit trail (RedactionRecord correctness)
    - Protocol compliance
    - Edge cases (empty, no secrets, multiple secrets, overlapping spans)
    - Fail-safe behaviour (sanitize() never raises)
    - Custom pattern injection
    - SanitizeResult properties
"""

from __future__ import annotations

import hashlib
import re

import pytest

from src.services.secret_sanitizer import (
    BUILT_IN_PATTERNS,
    RedactionRecord,
    SanitizeResult,
    SecretPattern,
    SecretSanitizer,
    SecretSanitizerProtocol,
    _looks_like_secret,
    _shannon_entropy,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def sanitizer() -> SecretSanitizer:
    return SecretSanitizer()


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


class TestProtocol:
    def test_secret_sanitizer_implements_protocol(self):
        assert isinstance(SecretSanitizer(), SecretSanitizerProtocol)

    def test_protocol_is_runtime_checkable(self):
        # Any object with sanitize() matches
        class Fake:
            def sanitize(self, text: str) -> SanitizeResult:
                return SanitizeResult(text=text, redactions=())

        assert isinstance(Fake(), SecretSanitizerProtocol)


# ---------------------------------------------------------------------------
# SanitizeResult
# ---------------------------------------------------------------------------


class TestSanitizeResult:
    def test_is_clean_when_no_redactions(self):
        r = SanitizeResult(text="hello", redactions=())
        assert r.is_clean is True

    def test_not_clean_when_redactions_present(self):
        record = RedactionRecord("test", 0, 5, _sha256("hello"))
        r = SanitizeResult(text="[REDACTED:test]", redactions=(record,))
        assert r.is_clean is False

    def test_result_is_frozen(self):
        r = SanitizeResult(text="x", redactions=())
        with pytest.raises(Exception):
            r.text = "y"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Clean input — no redaction
# ---------------------------------------------------------------------------


class TestCleanInput:
    def test_empty_string(self):
        result = sanitizer().sanitize("")
        assert result.text == ""
        assert result.is_clean

    def test_normal_log_line(self):
        text = "ERROR database connection refused at host 192.168.1.1 port 5432"
        result = sanitizer().sanitize(text)
        assert result.text == text
        assert result.is_clean

    def test_normal_stacktrace(self):
        text = (
            "Traceback (most recent call last):\n"
            '  File "app.py", line 42, in handler\n'
            "  ValueError: invalid input received"
        )
        result = sanitizer().sanitize(text)
        assert result.text == text
        assert result.is_clean

    def test_short_alphanumeric_not_flagged(self):
        # Under entropy min length — must not trigger entropy detection
        result = sanitizer().sanitize("abc123XYZ")
        assert result.is_clean


# ---------------------------------------------------------------------------
# AWS patterns
# ---------------------------------------------------------------------------


class TestAWSPatterns:
    def test_aws_access_key_redacted(self):
        text = "key=AKIAIOSFODNN7EXAMPLE and other stuff"
        result = sanitizer().sanitize(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in result.text
        assert "[REDACTED:aws-access-key]" in result.text

    def test_aws_access_key_audit_record(self):
        key = "AKIAIOSFODNN7EXAMPLE"
        text = f"key={key}"
        result = sanitizer().sanitize(text)
        assert not result.is_clean
        record = result.redactions[0]
        assert record.pattern_name == "aws-access-key"
        assert record.value_hash == _sha256(key)

    def test_aws_access_key_not_false_positive_on_short(self):
        # Only 15 chars after AKIA — too short
        result = sanitizer().sanitize("AKIA123456789AB")
        # Should not match (16 chars required after AKIA)
        assert "aws-access-key" not in str([r.pattern_name for r in result.redactions])


# ---------------------------------------------------------------------------
# GitHub tokens
# ---------------------------------------------------------------------------


class TestGitHubTokens:
    @pytest.mark.parametrize("prefix", ["ghp", "gho", "ghr", "ghs"])
    def test_github_token_variants(self, prefix: str):
        token = f"{prefix}_" + "A" * 36
        result = sanitizer().sanitize(f"Authorization: Bearer {token}")
        assert token not in result.text
        assert "[REDACTED:github-token]" in result.text

    def test_github_token_audit_name(self):
        token = "ghp_" + "B" * 36
        result = sanitizer().sanitize(token)
        assert result.redactions[0].pattern_name == "github-token"


# ---------------------------------------------------------------------------
# Stripe keys
# ---------------------------------------------------------------------------


class TestStripeKeys:
    def test_stripe_secret_key_redacted(self):
        key = "sk_live_" + "x" * 24
        result = sanitizer().sanitize(f"STRIPE_SECRET_KEY={key}")
        assert key not in result.text
        assert "[REDACTED:stripe-secret-key]" in result.text

    def test_stripe_restricted_key_redacted(self):
        key = "rk_live_" + "y" * 24
        result = sanitizer().sanitize(key)
        assert key not in result.text
        assert "[REDACTED:stripe-restricted]" in result.text

    def test_stripe_test_key_not_redacted(self):
        # sk_test_ is NOT a production secret — should not match sk_live_
        key = "sk_test_" + "z" * 24
        result = sanitizer().sanitize(key)
        # May or may not be flagged by entropy but NOT by stripe pattern
        stripe_records = [r for r in result.redactions if r.pattern_name == "stripe-secret-key"]
        assert len(stripe_records) == 0


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------


class TestJWTTokens:
    def test_jwt_token_redacted(self):
        jwt = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
            ".eyJzdWIiOiIxMjM0NTY3ODkwIn0"
            ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        result = sanitizer().sanitize(f"token={jwt}")
        assert jwt not in result.text
        assert "[REDACTED:jwt-token]" in result.text

    def test_jwt_audit_record_has_hash(self):
        jwt = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
            ".eyJzdWIiOiIxMjM0NTY3ODkwIn0"
            ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        result = sanitizer().sanitize(jwt)
        assert result.redactions[0].value_hash == _sha256(jwt)


# ---------------------------------------------------------------------------
# PEM private keys
# ---------------------------------------------------------------------------


class TestPEMKeys:
    @pytest.mark.parametrize("key_type", ["RSA ", "EC ", "OPENSSH ", ""])
    def test_pem_private_key_header_redacted(self, key_type: str):
        text = f"-----BEGIN {key_type}PRIVATE KEY-----\nMIIEpAIBAAKCAQEA..."
        result = sanitizer().sanitize(text)
        assert "[REDACTED:pem-private-key]" in result.text

    def test_pem_public_key_not_redacted(self):
        text = "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkq..."
        result = sanitizer().sanitize(text)
        pem_records = [r for r in result.redactions if r.pattern_name == "pem-private-key"]
        assert len(pem_records) == 0


# ---------------------------------------------------------------------------
# Generic API keys
# ---------------------------------------------------------------------------


class TestGenericAPIKeys:
    @pytest.mark.parametrize(
        "key_name",
        [
            "api_key",
            "API_KEY",
            "api-key",
            "apikey",
            "api_secret",
            "API_SECRET",
        ],
    )
    def test_generic_api_key_variants(self, key_name: str):
        text = f'{key_name} = "abcdefghijklmnopqrstuvwxyz123456"'
        result = sanitizer().sanitize(text)
        assert "[REDACTED:generic-api-key]" in result.text

    def test_short_generic_value_not_redacted(self):
        # Value under 16 chars — too short to be a real key
        text = 'api_key = "tooshort"'
        result = sanitizer().sanitize(text)
        generic_records = [r for r in result.redactions if r.pattern_name == "generic-api-key"]
        assert len(generic_records) == 0


# ---------------------------------------------------------------------------
# URL passwords
# ---------------------------------------------------------------------------


class TestURLPasswords:
    def test_url_password_redacted(self):
        text = "db_url = postgresql://admin:supersecretpassword@db.example.com/mydb"
        result = sanitizer().sanitize(text)
        assert "supersecretpassword" not in result.text
        assert "[REDACTED:url-password]" in result.text

    def test_url_without_password_not_redacted(self):
        text = "https://api.example.com/v1/endpoint"
        result = sanitizer().sanitize(text)
        url_records = [r for r in result.redactions if r.pattern_name == "url-password"]
        assert len(url_records) == 0

    def test_short_password_not_redacted(self):
        # Under 6 chars — not treated as a credential
        text = "ftp://user:pass@host"
        result = sanitizer().sanitize(text)
        url_records = [r for r in result.redactions if r.pattern_name == "url-password"]
        assert len(url_records) == 0


# ---------------------------------------------------------------------------
# Slack / Google / SendGrid / NPM / PyPI
# ---------------------------------------------------------------------------


class TestOtherPatterns:
    def test_slack_bot_token_redacted(self):
        token = "xoxb-INVALID-123456789012-1234567890123-abcdefghijklmnop"
        result = sanitizer().sanitize(token)
        assert "[REDACTED:slack-token]" in result.text

    def test_google_api_key_redacted(self):
        key = "AIza" + "A" * 35
        result = sanitizer().sanitize(key)
        assert "[REDACTED:google-api-key]" in result.text

    def test_npm_token_redacted(self):
        token = "npm_" + "A" * 36
        result = sanitizer().sanitize(token)
        assert "[REDACTED:npm-token]" in result.text

    def test_pypi_token_redacted(self):
        token = "pypi-" + "A" * 40
        result = sanitizer().sanitize(token)
        assert "[REDACTED:pypi-token]" in result.text

    def test_twilio_account_sid_redacted(self):
        sid = "AC" + "a" * 32
        result = sanitizer().sanitize(sid)
        assert "[REDACTED:twilio-account-sid]" in result.text


# ---------------------------------------------------------------------------
# Entropy detection
# ---------------------------------------------------------------------------


class TestEntropyDetection:
    def test_shannon_entropy_uniform(self):
        # "abcdefghijklmnopqrstuvwxyz" — maximum entropy for 26 chars
        entropy = _shannon_entropy("abcdefghijklmnopqrstuvwxyz")
        assert entropy > 4.0

    def test_shannon_entropy_single_char(self):
        assert _shannon_entropy("a" * 100) == 0.0

    def test_shannon_entropy_empty(self):
        assert _shannon_entropy("") == 0.0

    def test_looks_like_secret_high_entropy(self):
        # Simulate a random-looking API key
        token = "xK9mP2vQrL5nJ8wT3yA6bC1dE4fG7hI0"
        assert _looks_like_secret(token)

    def test_looks_like_secret_low_entropy(self):
        assert not _looks_like_secret("a" * 30)

    def test_looks_like_secret_too_short(self):
        assert not _looks_like_secret("xK9mP2vQrL5nJ8wT")  # 16 chars < 20

    def test_looks_like_secret_too_long(self):
        # Over 200 chars — skip (could be base64 doc, certificate body, etc.)
        assert not _looks_like_secret("A" * 201)

    def test_high_entropy_token_in_text_redacted(self):
        # Not a known pattern, but high entropy
        secret = "xK9mP2vQrL5nJ8wT3yA6bC1dE4fG7hI0"
        text = f"config value: {secret} end"
        result = sanitizer().sanitize(text)
        entropy_records = [r for r in result.redactions if r.pattern_name == "entropy"]
        assert len(entropy_records) >= 1

    def test_normal_prose_not_flagged_by_entropy(self):
        text = "The quick brown fox jumps over the lazy dog at the riverbank"
        result = sanitizer().sanitize(text)
        entropy_records = [r for r in result.redactions if r.pattern_name == "entropy"]
        assert len(entropy_records) == 0

    def test_entropy_detection_disabled(self):
        s = SecretSanitizer(entropy_detection=False)
        secret = "xK9mP2vQrL5nJ8wT3yA6bC1dE4fG7hI0"
        result = s.sanitize(f"value: {secret}")
        entropy_records = [r for r in result.redactions if r.pattern_name == "entropy"]
        assert len(entropy_records) == 0


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------


class TestAuditTrail:
    def test_record_has_correct_hash(self):
        key = "AKIAIOSFODNN7EXAMPLE"
        result = sanitizer().sanitize(key)
        assert result.redactions[0].value_hash == _sha256(key)

    def test_record_has_correct_offsets(self):
        prefix = "key="
        key = "AKIAIOSFODNN7EXAMPLE"
        text = prefix + key
        result = sanitizer().sanitize(text)
        record = result.redactions[0]
        assert record.start == len(prefix)
        assert record.end == len(prefix) + len(key)

    def test_record_is_frozen(self):
        key = "AKIAIOSFODNN7EXAMPLE"
        result = sanitizer().sanitize(key)
        with pytest.raises(Exception):
            result.redactions[0].pattern_name = "changed"  # type: ignore[misc]

    def test_audit_records_in_left_to_right_order(self):
        aws_key = "AKIAIOSFODNN7EXAMPLE"
        github_token = "ghp_" + "B" * 36
        text = f"{aws_key} ... {github_token}"
        result = sanitizer().sanitize(text)
        assert len(result.redactions) == 2
        assert result.redactions[0].start < result.redactions[1].start

    def test_no_plaintext_in_record(self):
        key = "AKIAIOSFODNN7EXAMPLE"
        result = sanitizer().sanitize(key)
        record = result.redactions[0]
        # Ensure the record fields contain no raw secret value
        assert key not in str(record.pattern_name)
        assert key not in str(record.value_hash)
        assert len(record.value_hash) == 64  # SHA-256 hex


# ---------------------------------------------------------------------------
# Multiple secrets in one text
# ---------------------------------------------------------------------------


class TestMultipleSecrets:
    def test_two_secrets_both_redacted(self):
        aws = "AKIAIOSFODNN7EXAMPLE"
        github = "ghp_" + "C" * 36
        text = f"aws={aws} github={github}"
        result = sanitizer().sanitize(text)
        assert aws not in result.text
        assert github not in result.text
        assert len(result.redactions) == 2

    def test_three_different_types_all_redacted(self):
        aws = "AKIAIOSFODNN7EXAMPLE"
        stripe = "sk_live_" + "d" * 24
        jwt = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
            ".eyJzdWIiOiIxMjM0NTY3ODkwIn0"
            ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        text = f"{aws} {stripe} {jwt}"
        result = sanitizer().sanitize(text)
        assert aws not in result.text
        assert stripe not in result.text
        assert jwt not in result.text

    def test_same_secret_twice_both_redacted(self):
        aws = "AKIAIOSFODNN7EXAMPLE"
        text = f"primary={aws} backup={aws}"
        result = sanitizer().sanitize(text)
        assert aws not in result.text
        assert len(result.redactions) == 2


# ---------------------------------------------------------------------------
# Custom patterns
# ---------------------------------------------------------------------------


class TestCustomPatterns:
    def test_custom_pattern_overrides_defaults(self):
        custom = SecretPattern(
            name="my-internal-key",
            pattern=re.compile(r"INT_KEY_[A-Z0-9]{8}"),
            label="internal-key",
        )
        s = SecretSanitizer(patterns=[custom])
        result = s.sanitize("config: INT_KEY_ABCD1234 end")
        assert "[REDACTED:internal-key]" in result.text

    def test_custom_pattern_does_not_apply_defaults(self):
        custom = SecretPattern(
            name="custom",
            pattern=re.compile(r"CUSTOM_[A-Z]+"),
            label="custom",
        )
        s = SecretSanitizer(patterns=[custom])
        # AWS key should NOT be redacted when defaults are replaced
        aws = "AKIAIOSFODNN7EXAMPLE"
        result = s.sanitize(aws)
        named_records = [r for r in result.redactions if r.pattern_name == "aws-access-key"]
        assert len(named_records) == 0


# ---------------------------------------------------------------------------
# Fail-safe behaviour
# ---------------------------------------------------------------------------


class TestFailSafe:
    def test_sanitize_never_raises_on_none_like_input(self):
        # Empty string edge
        result = sanitizer().sanitize("")
        assert isinstance(result, SanitizeResult)

    def test_sanitize_returns_safe_result_on_error(self):
        """Force an internal error and verify fail-safe triggers."""

        class BrokenSanitizer(SecretSanitizer):
            def _sanitize(self, text: str) -> SanitizeResult:
                raise RuntimeError("simulated internal failure")

        s = BrokenSanitizer()
        result = s.sanitize("any text")
        assert result.text == "[REDACTED: sanitizer error]"
        assert result.is_clean  # no partial audit records on error


# ---------------------------------------------------------------------------
# Built-in patterns catalogue
# ---------------------------------------------------------------------------


class TestBuiltInPatternsCatalogue:
    def test_built_in_patterns_is_tuple(self):
        assert isinstance(BUILT_IN_PATTERNS, tuple)

    def test_all_patterns_have_names(self):
        for p in BUILT_IN_PATTERNS:
            assert p.name, f"Pattern missing name: {p}"

    def test_all_patterns_have_compiled_regex(self):
        for p in BUILT_IN_PATTERNS:
            assert isinstance(p.pattern, re.Pattern), f"{p.name} pattern not compiled"

    def test_all_patterns_have_labels(self):
        for p in BUILT_IN_PATTERNS:
            assert p.label, f"Pattern {p.name} missing label"

    def test_minimum_pattern_count(self):
        # Ensure we haven't accidentally stripped patterns
        assert len(BUILT_IN_PATTERNS) >= 10
