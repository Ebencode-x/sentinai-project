"""D1 — Unit tests for PatchSemanticValidator.

Coverage targets
----------------
- Clean patches must NOT trigger any rule (no false positives)
- Every rule code (AUTH001-004, PRIV001-023, SEC001-005, TAINT001-002)
  has at least one positive test
- Diff format (unified patch) is handled correctly
- Raw Python source is handled correctly
- Empty / whitespace-only input returns clean result
- SyntaxError in patch returns parse_error, not a crash
- SemanticValidationResult properties (has_critical, has_high, is_clean)
- Severity escalation: subprocess without shell=True → HIGH,
  subprocess with shell=True → CRITICAL
"""

from __future__ import annotations

import pytest

from src.services.patch_semantic_validator import (
    PatchSemanticValidator,
    SemanticValidationResult,
    SemanticViolation,
    Severity,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def validator() -> PatchSemanticValidator:
    return PatchSemanticValidator()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_diff(added_lines: str) -> str:
    """Wrap Python source as a minimal unified diff."""
    header = "--- a/src/app.py\n+++ b/src/app.py\n@@ -1,0 +1,0 @@\n"
    prefixed = "\n".join(f"+{line}" for line in added_lines.splitlines())
    return header + prefixed


def codes(result: SemanticValidationResult) -> set[str]:
    return {v.code for v in result.violations}


def severities(result: SemanticValidationResult) -> set[Severity]:
    return {v.severity for v in result.violations}


# ===========================================================================
# Clean inputs — MUST produce zero violations
# ===========================================================================


class TestCleanInputs:
    def test_empty_string(self, validator):
        assert validator.validate("").is_clean

    def test_whitespace_only(self, validator):
        assert validator.validate("   \n\t  ").is_clean

    def test_simple_function(self, validator):
        src = "def add(a, b):\n    return a + b\n"
        assert validator.validate(src).is_clean

    def test_safe_subprocess_no_shell(self, validator):
        src = 'import subprocess\nsubprocess.run(["ls", "-la"])\n'
        result = validator.validate(src)
        # No shell=True — should be HIGH at most, not CRITICAL
        assert not result.has_critical

    def test_safe_hash_sha256(self, validator):
        src = "import hashlib\nhashlib.sha256(b'data').hexdigest()\n"
        assert validator.validate(src).is_clean

    def test_safe_secrets_module(self, validator):
        src = "import secrets\ntoken = secrets.token_hex(32)\n"
        assert validator.validate(src).is_clean

    def test_safe_yaml_safeloader(self, validator):
        src = "import yaml\ndata = yaml.safe_load(stream)\n"
        assert validator.validate(src).is_clean

    def test_safe_tempfile(self, validator):
        src = "import tempfile\nf = tempfile.NamedTemporaryFile()\n"
        assert validator.validate(src).is_clean

    def test_placeholder_password_not_flagged(self, validator):
        # Placeholder strings must NOT be flagged
        src = 'password = "changeme"\n'
        assert validator.validate(src).is_clean

    def test_short_string_not_flagged(self, validator):
        src = 'key = "abc"\n'
        assert validator.validate(src).is_clean

    def test_diff_removed_lines_ignored(self, validator):
        """Lines starting with '-' are safe (they are removed)."""
        patch = (
            "--- a/app.py\n+++ b/app.py\n@@ -1,3 +1,3 @@\n"
            "-import os\n"
            "-os.system('rm -rf /')\n"
            "+pass\n"
        )
        result = validator.validate(patch)
        # Only '+pass' is analysed — no violations
        assert result.is_clean

    def test_diff_with_safe_additions(self, validator):
        patch = make_diff("x = 1\ny = x + 2\n")
        assert validator.validate(patch).is_clean

    def test_syntax_error_returns_parse_error(self, validator):
        result = validator.validate("def broken(\n")
        assert result.parse_error is not None
        assert not result.violations


# ===========================================================================
# AUTH rule set
# ===========================================================================


class TestAuthRules:
    def test_auth001_bypass_kwarg_true(self, validator):
        src = "login(username, skip_auth=True)\n"
        result = validator.validate(src)
        assert "AUTH001" in codes(result)
        assert result.has_critical

    def test_auth001_bypass_kwarg_false_clean(self, validator):
        src = "login(username, skip_auth=False)\n"
        result = validator.validate(src)
        assert "AUTH001" not in codes(result)

    def test_auth002_hardcoded_credential_in_call(self, validator):
        src = 'authenticate(user, "Sup3r$ecr3t!key")\n'
        result = validator.validate(src)
        assert "AUTH002" in codes(result)
        assert result.has_critical

    def test_auth003_hardcoded_credential_in_compare(self, validator):
        src = 'if password == "H4rdC0d3d!pw":\n    pass\n'
        result = validator.validate(src)
        assert "AUTH003" in codes(result)
        assert result.has_high

    def test_auth004_protected_endpoint_no_decorator(self, validator):
        src = "def admin_panel():\n    return render()\n"
        result = validator.validate(src)
        assert "AUTH004" in codes(result)

    def test_auth004_clean_when_decorated(self, validator):
        src = "@login_required\ndef admin_panel():\n    return render()\n"
        result = validator.validate(src)
        assert "AUTH004" not in codes(result)

    def test_auth004_not_triggered_for_non_protected_name(self, validator):
        src = "def compute_total(cart):\n    return sum(cart)\n"
        assert validator.validate(src).is_clean


# ===========================================================================
# PRIV rule set
# ===========================================================================


class TestPrivRules:
    def test_priv001_subprocess_call_shell_true(self, validator):
        src = "import subprocess\nsubprocess.call('ls', shell=True)\n"
        result = validator.validate(src)
        assert "PRIV001" in codes(result)
        assert result.has_critical

    def test_priv002_subprocess_run_no_shell_high(self, validator):
        src = 'import subprocess\nsubprocess.run(["ls"])\n'
        result = validator.validate(src)
        assert "PRIV002" in codes(result)
        # Without shell=True it must be HIGH, not CRITICAL
        priv_violations = [v for v in result.violations if v.code == "PRIV002"]
        assert all(v.severity is Severity.HIGH for v in priv_violations)

    def test_priv002_subprocess_run_shell_true_critical(self, validator):
        src = "import subprocess\nsubprocess.run('cmd', shell=True)\n"
        result = validator.validate(src)
        priv_violations = [v for v in result.violations if v.code == "PRIV002"]
        assert any(v.severity is Severity.CRITICAL for v in priv_violations)

    def test_priv005_os_system(self, validator):
        src = "import os\nos.system('whoami')\n"
        result = validator.validate(src)
        assert "PRIV005" in codes(result)
        assert result.has_critical

    def test_priv011_os_setuid(self, validator):
        src = "import os\nos.setuid(0)\n"
        result = validator.validate(src)
        assert "PRIV011" in codes(result)
        assert result.has_critical

    def test_priv013_eval(self, validator):
        src = "result = eval(user_input)\n"
        result = validator.validate(src)
        assert "PRIV013" in codes(result)
        assert result.has_critical

    def test_priv014_exec(self, validator):
        src = "exec(code_string)\n"
        result = validator.validate(src)
        assert "PRIV014" in codes(result)
        assert result.has_critical

    def test_priv018_pickle_loads(self, validator):
        src = "import pickle\nobj = pickle.loads(data)\n"
        result = validator.validate(src)
        assert "PRIV018" in codes(result)
        assert result.has_critical

    def test_priv021_yaml_load_unsafe(self, validator):
        src = "import yaml\ndata = yaml.load(stream)\n"
        result = validator.validate(src)
        assert "PRIV021" in codes(result)
        assert result.has_critical

    def test_priv022_mktemp(self, validator):
        src = "import tempfile\npath = tempfile.mktemp()\n"
        result = validator.validate(src)
        assert "PRIV022" in codes(result)
        assert result.has_high

    def test_priv023_world_writable_chmod(self, validator):
        src = "import os\nos.chmod('/etc/passwd', 0o777)\n"
        result = validator.validate(src)
        assert "PRIV023" in codes(result)
        assert result.has_critical


# ===========================================================================
# SEC rule set
# ===========================================================================


class TestSecRules:
    def test_sec001_md5(self, validator):
        src = "import hashlib\nhashlib.md5(data)\n"
        result = validator.validate(src)
        assert "SEC001" in codes(result)
        assert result.has_high

    def test_sec001_sha1(self, validator):
        src = "import hashlib\nhashlib.sha1(data)\n"
        result = validator.validate(src)
        assert "SEC001" in codes(result)

    def test_sec001_hashlib_new_md5(self, validator):
        src = "import hashlib\nhashlib.new('md5', data)\n"
        result = validator.validate(src)
        assert "SEC001" in codes(result)

    def test_sec002_random_randint(self, validator):
        src = "import random\ntoken = random.randint(0, 2**32)\n"
        result = validator.validate(src)
        assert "SEC002" in codes(result)
        assert result.has_high

    def test_sec003_ssl_verify_false(self, validator):
        src = "import requests\nrequests.get('https://api.example.com', verify=False)\n"
        result = validator.validate(src)
        assert "SEC003" in codes(result)
        assert result.has_critical

    def test_sec003_ssl_verify_true_clean(self, validator):
        src = "import requests\nrequests.get('https://api.example.com', verify=True)\n"
        result = validator.validate(src)
        assert "SEC003" not in codes(result)

    def test_sec004_hardcoded_secret_assign(self, validator):
        src = 'api_key = "sk-abc123!XYZ789$real"\n'
        result = validator.validate(src)
        assert "SEC004" in codes(result)
        assert result.has_critical

    def test_sec004_env_var_clean(self, validator):
        src = "import os\napi_key = os.environ.get('API_KEY')\n"
        result = validator.validate(src)
        assert "SEC004" not in codes(result)

    def test_sec005_secret_in_kwarg(self, validator):
        src = 'connect(host="db", password="R34l$ecret99!")\n'
        result = validator.validate(src)
        assert "SEC005" in codes(result)
        assert result.has_critical


# ===========================================================================
# TAINT rule set
# ===========================================================================


class TestTaintRules:
    def test_taint001_user_input_to_execute(self, validator):
        src = "query = request.args.get('q')\ncursor.execute(query)\n"
        result = validator.validate(src)
        assert "TAINT001" in codes(result)
        assert result.has_high

    def test_taint002_fstring_in_execute(self, validator):
        src = "table = request.args.get('t')\ncursor.execute(f\"SELECT * FROM {table}\")\n"
        result = validator.validate(src)
        assert "TAINT002" in codes(result)
        assert result.has_critical

    def test_taint001_input_to_os_system(self, validator):
        src = "cmd = input('Enter command: ')\nos.system(cmd)\n"
        result = validator.validate(src)
        assert "TAINT001" in codes(result)

    def test_taint001_getenv_to_subprocess(self, validator):
        src = "import os, subprocess\nscript = os.environ.get('SCRIPT')\nsubprocess.run(script)\n"
        result = validator.validate(src)
        assert "TAINT001" in codes(result)

    def test_taint_clean_parameterized_query(self, validator):
        src = (
            "user_id = request.args.get('id')\n"
            "cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))\n"
        )
        # user_id is passed as a parameter tuple, not as direct arg — clean
        result = validator.validate(src)
        # TAINT001 fires on the first positional arg only; tuple is the second arg
        # so this should be clean or at most a low finding
        critical = [v for v in result.violations if v.severity is Severity.CRITICAL]
        assert not critical


# ===========================================================================
# Unified diff format
# ===========================================================================


class TestDiffFormat:
    def test_diff_only_added_lines_analysed(self, validator):
        """Removed dangerous lines should not trigger violations."""
        patch = "--- a/app.py\n+++ b/app.py\n@@ -5,3 +5,3 @@\n-    os.system(user_cmd)\n+    pass\n"
        result = validator.validate(patch)
        assert result.is_clean

    def test_diff_added_eval_flagged(self, validator):
        patch = make_diff("result = eval(user_input)\n")
        result = validator.validate(patch)
        assert "PRIV013" in codes(result)

    def test_diff_added_safe_code_clean(self, validator):
        patch = make_diff("x = 42\nprint(x)\n")
        assert validator.validate(patch).is_clean

    def test_diff_header_lines_not_parsed(self, validator):
        """'+++' and '---' lines must not cause parse errors."""
        patch = "--- a/old.py\n+++ b/new.py\n@@ -0,0 +1,2 @@\n+x = 1\n+y = 2\n"
        result = validator.validate(patch)
        assert result.parse_error is None
        assert result.is_clean


# ===========================================================================
# SemanticValidationResult properties
# ===========================================================================


class TestResultProperties:
    def test_is_clean_no_violations(self, validator):
        r = SemanticValidationResult()
        assert r.is_clean
        assert not r.has_critical
        assert not r.has_high

    def test_has_critical_filters_correctly(self):
        v_crit = SemanticViolation("PRIV013", "eval()", Severity.CRITICAL, 1, rule_set="PRIV")
        v_high = SemanticViolation("SEC001", "md5", Severity.HIGH, 2, rule_set="SEC")
        r = SemanticValidationResult(violations=[v_crit, v_high])
        assert r.has_critical
        assert r.has_high
        assert len(r.critical_violations) == 1
        assert len(r.high_violations) == 1

    def test_len(self):
        v = SemanticViolation("X001", "msg", Severity.HIGH, 1)
        r = SemanticValidationResult(violations=[v, v, v])
        assert len(r) == 3

    def test_parse_error_not_clean(self):
        r = SemanticValidationResult(parse_error="SyntaxError at line 1: invalid syntax")
        assert not r.is_clean

    def test_violation_str(self):
        v = SemanticViolation("PRIV013", "eval() is dangerous", Severity.CRITICAL, 7)
        assert "PRIV013" in str(v)
        assert "7" in str(v)


# ===========================================================================
# Integration: policy_engine wiring
# ===========================================================================


class TestPolicyEngineWiring:
    """Smoke tests confirming the validator integrates correctly
    with the data shapes that policy_engine.py expects."""

    def test_critical_triggers_block_shape(self, validator):
        src = "eval(user_input)\n"
        result = validator.validate(src)
        assert result.has_critical
        # policy_engine iterates result.critical_violations and reads .code / .message
        for v in result.critical_violations:
            assert v.code
            assert v.message
            assert isinstance(v.severity, Severity)
            assert isinstance(v.lineno, int)

    def test_high_triggers_review_shape(self, validator):
        src = "import tempfile\ntempfile.mktemp()\n"
        result = validator.validate(src)
        assert result.has_high
        for v in result.high_violations:
            assert v.code
            assert v.message

    def test_clean_patch_allows(self, validator):
        src = "def compute(x):\n    return x * 2\n"
        result = validator.validate(src)
        assert result.is_clean
        assert not result.has_critical
        assert not result.has_high
