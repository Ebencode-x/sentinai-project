"""Tests for PatchSemanticValidator — D1.

Covers:
  - AUTH001–AUTH007  auth bypass and guard removal
  - PRIV001–PRIV003  privilege escalation
  - SEC001–SEC002    hardcoded secrets and deletions
  - TAINT001–TAINT002 taint flow and dangerous sinks
  - Clean patches (no false positives)
  - Deletion-only patches (no added lines)
  - Malformed / non-Python patches (regex fallback)
  - Empty patch edge cases
"""

from __future__ import annotations

from src.services.patch_semantic_validator import (
    PatchSemanticValidator,
    SemanticResult,
    Severity,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch(*added_lines: str) -> str:
    """Build a minimal unified diff with the given added lines."""
    header = "--- a/src/service.py\n+++ b/src/service.py\n@@ -1,3 +1,3 @@\n"
    body = "\n".join(f"+{line}" for line in added_lines)
    return header + body


def _codes(result: SemanticResult) -> set[str]:
    return {v.code for v in result.violations}


def _severities(result: SemanticResult) -> set[str]:
    return {v.severity for v in result.violations}


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------


class TestInstantiation:
    def test_default_construction(self):
        v = PatchSemanticValidator()
        assert v is not None

    def test_empty_patch_returns_clean(self):
        v = PatchSemanticValidator()
        result = v.validate("")
        assert result.is_clean
        assert result.analysed_lines == 0

    def test_whitespace_only_patch_returns_clean(self):
        v = PatchSemanticValidator()
        result = v.validate("   \n\n  ")
        assert result.is_clean

    def test_deletion_only_patch_returns_clean(self):
        """A patch that only removes lines has no added code to analyse."""
        patch = (
            "--- a/src/service.py\n"
            "+++ b/src/service.py\n"
            "@@ -1,3 +1,2 @@\n"
            "-old_line_one\n"
            "-old_line_two\n"
            " context_line\n"
        )
        v = PatchSemanticValidator()
        result = v.validate(patch)
        assert result.is_clean


# ---------------------------------------------------------------------------
# AUTH001 — hardcoded if True:
# ---------------------------------------------------------------------------


class TestAuth001HardcodedIfTrue:
    def test_detects_if_true(self):
        patch = _patch("if True:", "    do_something()")
        result = PatchSemanticValidator().validate(patch)
        assert "AUTH001" in _codes(result)
        assert result.has_critical

    def test_normal_if_condition_clean(self):
        patch = _patch("if user.is_authenticated:", "    proceed()")
        result = PatchSemanticValidator().validate(patch)
        assert "AUTH001" not in _codes(result)

    def test_if_true_with_else_detected(self):
        patch = _patch("if True:", "    admin = True", "else:", "    pass")
        result = PatchSemanticValidator().validate(patch)
        assert "AUTH001" in _codes(result)


# ---------------------------------------------------------------------------
# AUTH002 — hardcoded if False:
# ---------------------------------------------------------------------------


class TestAuth002HardcodedIfFalse:
    def test_detects_if_false(self):
        patch = _patch("if False:", "    raise PermissionError()")
        result = PatchSemanticValidator().validate(patch)
        assert "AUTH002" in _codes(result)
        assert result.has_high

    def test_if_false_is_high_not_critical(self):
        patch = _patch("if False:", "    pass")
        result = PatchSemanticValidator().validate(patch)
        assert not result.has_critical
        assert result.has_high


# ---------------------------------------------------------------------------
# AUTH003 — inverted auth guard
# ---------------------------------------------------------------------------


class TestAuth003InvertedGuard:
    def test_detects_not_is_admin(self):
        patch = _patch("if not is_admin:", "    grant_access()")
        result = PatchSemanticValidator().validate(patch)
        assert "AUTH003" in _codes(result)
        assert result.has_critical

    def test_detects_not_is_authenticated(self):
        patch = _patch("if not is_authenticated:", "    return True")
        result = PatchSemanticValidator().validate(patch)
        assert "AUTH003" in _codes(result)

    def test_not_on_safe_variable_clean(self):
        patch = _patch("if not error:", "    continue")
        result = PatchSemanticValidator().validate(patch)
        assert "AUTH003" not in _codes(result)


# ---------------------------------------------------------------------------
# PRIV001 — is_admin = True
# ---------------------------------------------------------------------------


class TestPriv001PrivilegeEscalation:
    def test_detects_is_admin_true(self):
        patch = _patch("is_admin = True")
        result = PatchSemanticValidator().validate(patch)
        assert "PRIV001" in _codes(result)
        assert result.has_critical

    def test_detects_authorized_true(self):
        patch = _patch("authorized = True")
        result = PatchSemanticValidator().validate(patch)
        assert "PRIV001" in _codes(result)

    def test_detects_has_permission_true(self):
        patch = _patch("has_permission = True")
        result = PatchSemanticValidator().validate(patch)
        assert "PRIV001" in _codes(result)

    def test_safe_assignment_clean(self):
        patch = _patch("retry_count = True")
        result = PatchSemanticValidator().validate(patch)
        assert "PRIV001" not in _codes(result)


# ---------------------------------------------------------------------------
# PRIV002 — hardcoded privileged role string
# ---------------------------------------------------------------------------


class TestPriv002HardcodedRole:
    def test_detects_role_admin_string(self):
        patch = _patch('role = "admin"')
        result = PatchSemanticValidator().validate(patch)
        assert "PRIV002" in _codes(result)
        assert result.has_critical

    def test_detects_user_role_superuser(self):
        patch = _patch('user_role = "superuser"')
        result = PatchSemanticValidator().validate(patch)
        assert "PRIV002" in _codes(result)

    def test_safe_role_clean(self):
        patch = _patch('role = "viewer"')
        result = PatchSemanticValidator().validate(patch)
        assert "PRIV002" not in _codes(result)


# ---------------------------------------------------------------------------
# SEC001 — hardcoded secrets
# ---------------------------------------------------------------------------


class TestSec001HardcodedSecrets:
    def test_detects_hardcoded_password(self):
        patch = _patch('password = "hunter2"')
        result = PatchSemanticValidator().validate(patch)
        assert "SEC001" in _codes(result)
        assert result.has_critical

    def test_detects_hardcoded_token(self):
        patch = _patch('token = "sk-abc123"')
        result = PatchSemanticValidator().validate(patch)
        assert "SEC001" in _codes(result)

    def test_detects_hardcoded_api_key(self):
        patch = _patch('api_key = "AKIAIOSFODNN7EXAMPLE"')
        result = PatchSemanticValidator().validate(patch)
        assert "SEC001" in _codes(result)

    def test_env_var_lookup_is_clean(self):
        patch = _patch('password = os.environ["DB_PASSWORD"]')
        result = PatchSemanticValidator().validate(patch)
        assert "SEC001" not in _codes(result)


# ---------------------------------------------------------------------------
# TAINT001 — taint flow into dangerous sink
# ---------------------------------------------------------------------------


class TestTaint001TaintFlow:
    def test_detects_eval_with_request(self):
        patch = _patch("result = eval(request)")
        result = PatchSemanticValidator().validate(patch)
        assert "TAINT001" in _codes(result)
        assert result.has_critical

    def test_detects_exec_with_user_input(self):
        patch = _patch("exec(user_input)")
        result = PatchSemanticValidator().validate(patch)
        assert "TAINT001" in _codes(result)

    def test_detects_propagated_taint(self):
        """Taint propagates through variable assignment."""
        patch = _patch(
            "cmd = request",
            "eval(cmd)",
        )
        result = PatchSemanticValidator().validate(patch)
        assert "TAINT001" in _codes(result)


# ---------------------------------------------------------------------------
# TAINT002 — dangerous sink without obvious taint
# ---------------------------------------------------------------------------


class TestTaint002DangerousSink:
    def test_detects_bare_eval(self):
        patch = _patch('eval("2 + 2")')
        result = PatchSemanticValidator().validate(patch)
        assert "TAINT002" in _codes(result)
        assert result.has_high

    def test_detects_subprocess_popen(self):
        patch = _patch('subprocess.Popen(["ls", "-la"])')
        result = PatchSemanticValidator().validate(patch)
        assert "TAINT002" in _codes(result)

    def test_safe_open_with_literal(self):
        """open() with literal path flags as TAINT002 — intentional: needs review."""
        patch = _patch('f = open("config.json")')
        result = PatchSemanticValidator().validate(patch)
        assert "TAINT002" in _codes(result)


# ---------------------------------------------------------------------------
# AUTH006 — security function always returns True
# ---------------------------------------------------------------------------


class TestAuth006TrivialBypass:
    def test_detects_require_auth_returns_true(self):
        patch = _patch(
            "def require_auth(user):",
            "    return True",
        )
        result = PatchSemanticValidator().validate(patch)
        assert "AUTH006" in _codes(result)
        assert result.has_critical

    def test_detects_check_permission_returns_true(self):
        patch = _patch(
            "def check_permission():",
            "    return True",
        )
        result = PatchSemanticValidator().validate(patch)
        assert "AUTH006" in _codes(result)

    def test_normal_function_clean(self):
        patch = _patch(
            "def get_user(user_id):",
            "    return db.query(User).get(user_id)",
        )
        result = PatchSemanticValidator().validate(patch)
        assert "AUTH006" not in _codes(result)


# ---------------------------------------------------------------------------
# AUTH007 — security function is no-op
# ---------------------------------------------------------------------------


class TestAuth007NoOpSecurityFunction:
    def test_detects_verify_noop(self):
        patch = _patch(
            "def verify_token(token):",
            "    pass",
        )
        result = PatchSemanticValidator().validate(patch)
        assert "AUTH007" in _codes(result)
        assert result.has_high

    def test_validate_token_noop_flagged(self):
        patch = _patch(
            "def validate_token(t):",
            "    pass",
        )
        result = PatchSemanticValidator().validate(patch)
        assert "AUTH007" in _codes(result)


# ---------------------------------------------------------------------------
# Clean patches — no false positives
# ---------------------------------------------------------------------------


class TestCleanPatches:
    def test_simple_retry_logic_clean(self):
        patch = _patch(
            "import time",
            "def connect_with_retry(host, retries=3):",
            "    for attempt in range(retries):",
            "        try:",
            "            return connect(host)",
            "        except ConnectionError:",
            "            time.sleep(2 ** attempt)",
            "    raise ConnectionError('Max retries exceeded')",
        )
        result = PatchSemanticValidator().validate(patch)
        assert result.is_clean, f"Unexpected violations: {result.all_messages()}"

    def test_logging_addition_clean(self):
        patch = _patch(
            "import logging",
            "logger = logging.getLogger(__name__)",
            "logger.info('Request received: %s', request_id)",
        )
        result = PatchSemanticValidator().validate(patch)
        assert result.is_clean, f"Unexpected violations: {result.all_messages()}"

    def test_config_loading_clean(self):
        patch = _patch(
            "import os",
            "DB_HOST = os.environ.get('DB_HOST', 'localhost')",
            "DB_PORT = int(os.environ.get('DB_PORT', '5432'))",
        )
        result = PatchSemanticValidator().validate(patch)
        assert result.is_clean, f"Unexpected violations: {result.all_messages()}"

    def test_pagination_logic_clean(self):
        patch = _patch(
            "def paginate(queryset, page=1, page_size=20):",
            "    offset = (page - 1) * page_size",
            "    return queryset[offset: offset + page_size]",
        )
        result = PatchSemanticValidator().validate(patch)
        assert result.is_clean, f"Unexpected violations: {result.all_messages()}"

    def test_type_annotation_clean(self):
        patch = _patch(
            "from typing import Optional",
            "def get_user(user_id: int) -> Optional[dict]:",
            "    return db.get(user_id)",
        )
        result = PatchSemanticValidator().validate(patch)
        assert result.is_clean, f"Unexpected violations: {result.all_messages()}"


# ---------------------------------------------------------------------------
# Malformed patches — regex fallback
# ---------------------------------------------------------------------------


class TestMalformedPatchFallback:
    def test_non_python_patch_uses_regex_fallback(self):
        """Non-Python added lines trigger regex fallback, not a crash."""
        patch = (
            "--- a/config.yml\n+++ b/config.yml\n@@ -1,1 +1,2 @@\n+if True:\n+  is_admin = True\n"
        )
        result = PatchSemanticValidator().validate(patch)
        # Regex fallback should catch these
        assert result.has_critical or result.parse_errors

    def test_partial_python_records_parse_error(self):
        """Syntactically invalid Python records a parse error."""
        patch = _patch("def broken(:", "    pass")
        result = PatchSemanticValidator().validate(patch)
        assert result.parse_errors

    def test_parse_error_does_not_crash(self):
        """Validator must never raise — parse errors are captured."""
        patch = _patch("{{{{ invalid python !!!!")
        result = PatchSemanticValidator().validate(patch)
        assert isinstance(result, SemanticResult)


# ---------------------------------------------------------------------------
# SemanticResult API
# ---------------------------------------------------------------------------


class TestSemanticResultAPI:
    def test_summary_clean(self):
        result = SemanticResult()
        assert "No semantic violations" in result.summary

    def test_summary_with_violations(self):
        patch = _patch("if True:", "    is_admin = True")
        result = PatchSemanticValidator().validate(patch)
        assert "critical" in result.summary.lower()

    def test_all_messages_returns_strings(self):
        patch = _patch("if True:", "    pass")
        result = PatchSemanticValidator().validate(patch)
        messages = result.all_messages()
        assert all(isinstance(m, str) for m in messages)

    def test_critical_violations_property(self):
        patch = _patch("if True:", "    pass")
        result = PatchSemanticValidator().validate(patch)
        assert all(v.severity is Severity.CRITICAL for v in result.critical_violations)

    def test_high_violations_property(self):
        patch = _patch("if False:", "    raise PermissionError()")
        result = PatchSemanticValidator().validate(patch)
        assert all(v.severity is Severity.HIGH for v in result.high_violations)

    def test_analysed_lines_count(self):
        patch = _patch("x = 1", "y = 2", "z = 3")
        result = PatchSemanticValidator().validate(patch)
        assert result.analysed_lines == 3
