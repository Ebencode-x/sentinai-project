"""AST Semantic Patch Validator — D1.

Performs deep structural analysis of AI-proposed patches beyond simple
pattern matching. Parses Python source using the standard ``ast`` module
to detect:

  - Auth/authorization bypasses  (if True:, hardcoded roles)
  - Privilege escalation patterns (is_admin = True, role overrides)
  - Dangerous taint flows         (user input → exec/eval/subprocess)
  - Hardcoded secrets             (password = "...", token = "...")
  - Security control removal      (deletion of auth/permission checks)
  - Comparison weakening          (== replaced with ``is`` on booleans,
                                   ``not`` guards removed)

Architecture
------------
SemanticViolation   — immutable finding (severity + message + line)
SemanticResult      — aggregated findings for one analysis run
PatchSemanticValidator — main entry point; accepts raw unified-diff text

Integration
-----------
Called by PatchPolicyEngine.check() as step 7 — after pattern checks,
before the final ALLOW decision.  Any CRITICAL finding escalates the
decision to BLOCK; any HIGH finding escalates to REVIEW.
"""

from __future__ import annotations

import ast
import logging
import re
import textwrap
from dataclasses import dataclass, field
from enum import StrEnum

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


class Severity(StrEnum):
    CRITICAL = "critical"  # → BLOCK immediately
    HIGH = "high"  # → REVIEW required
    MEDIUM = "medium"  # → flagged, logged
    LOW = "low"  # → informational


@dataclass(frozen=True)
class SemanticViolation:
    """A single detected security issue."""

    severity: Severity
    code: str  # e.g. "AUTH001"
    message: str
    line: int | None = None
    node_type: str | None = None

    def __str__(self) -> str:
        loc = f" (line {self.line})" if self.line else ""
        return f"[{self.severity.upper()}] {self.code}{loc}: {self.message}"


@dataclass
class SemanticResult:
    """Aggregated result of one semantic analysis run."""

    violations: list[SemanticViolation] = field(default_factory=list)
    parse_errors: list[str] = field(default_factory=list)
    analysed_lines: int = 0

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def has_critical(self) -> bool:
        return any(v.severity is Severity.CRITICAL for v in self.violations)

    @property
    def has_high(self) -> bool:
        return any(v.severity is Severity.HIGH for v in self.violations)

    @property
    def is_clean(self) -> bool:
        return not self.violations and not self.parse_errors

    @property
    def critical_violations(self) -> list[SemanticViolation]:
        return [v for v in self.violations if v.severity is Severity.CRITICAL]

    @property
    def high_violations(self) -> list[SemanticViolation]:
        return [v for v in self.violations if v.severity is Severity.HIGH]

    @property
    def summary(self) -> str:
        if self.is_clean:
            return "No semantic violations detected."
        parts = []
        counts = {}
        for v in self.violations:
            counts[v.severity] = counts.get(v.severity, 0) + 1
        for sev in (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW):
            if sev in counts:
                parts.append(f"{counts[sev]} {sev}")
        if self.parse_errors:
            parts.append(f"{len(self.parse_errors)} parse error(s)")
        return "Semantic violations: " + ", ".join(parts)

    def all_messages(self) -> list[str]:
        return [str(v) for v in self.violations] + [f"[PARSE ERROR] {e}" for e in self.parse_errors]


# ---------------------------------------------------------------------------
# AST visitor — core analysis engine
# ---------------------------------------------------------------------------

# Security-sensitive identifiers — any assignment/comparison involving
# these names triggers deeper inspection.
_AUTH_NAMES: frozenset[str] = frozenset(
    {
        "is_admin",
        "is_superuser",
        "is_staff",
        "is_authenticated",
        "has_permission",
        "role",
        "roles",
        "user_role",
        "permission",
        "permissions",
        "access_level",
        "privilege",
        "privileges",
        "authorized",
        "allow",
        "allowed",
        "can_access",
        "user_type",
        "admin",
        "superuser",
    }
)

# Identifiers whose values must never be hardcoded in patches.
_SECRET_NAMES: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "auth_token",
        "access_token",
        "refresh_token",
        "private_key",
        "signing_key",
        "encryption_key",
        "credentials",
        "credential",
        "jwt_secret",
        "session_key",
        "secret_key",
    }
)

# Functions whose call with unsanitised input constitutes a taint sink.
_TAINT_SINKS: frozenset[str] = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "os.system",
        "subprocess.call",
        "subprocess.run",
        "subprocess.Popen",
        "open",
        "pickle.loads",
        "yaml.load",
        "marshal.loads",
        "__import__",
        "importlib.import_module",
    }
)

# Variable names that represent user-controlled / untrusted input.
_TAINT_SOURCES: frozenset[str] = frozenset(
    {
        "request",
        "input",
        "user_input",
        "query",
        "params",
        "args",
        "kwargs",
        "data",
        "body",
        "form",
        "payload",
        "raw",
        "content",
        "message",
        "cmd",
        "command",
        "user_data",
        "user_query",
    }
)


class _SecurityVisitor(ast.NodeVisitor):
    """Walk an AST and collect semantic security violations."""

    def __init__(self) -> None:
        self.violations: list[SemanticViolation] = []
        # Tracks names assigned from taint sources in current scope.
        self._tainted: set[str] = set()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _add(
        self,
        severity: Severity,
        code: str,
        message: str,
        node: ast.AST | None = None,
    ) -> None:
        line = getattr(node, "lineno", None)
        node_type = type(node).__name__ if node else None
        self.violations.append(
            SemanticViolation(
                severity=severity,
                code=code,
                message=message,
                line=line,
                node_type=node_type,
            )
        )

    def _name_of(self, node: ast.expr) -> str | None:
        """Best-effort extraction of a simple name from an expression."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return None

    def _is_literal_true(self, node: ast.expr) -> bool:
        return isinstance(node, ast.Constant) and node.value is True

    def _is_literal_false(self, node: ast.expr) -> bool:
        return isinstance(node, ast.Constant) and node.value is False

    def _is_nonempty_string(self, node: ast.expr) -> bool:
        return isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value

    def _call_name(self, node: ast.Call) -> str:
        """Return dotted name of a Call node, e.g. 'subprocess.Popen'."""
        func = node.func
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            parts = []
            cur: ast.expr = func
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
            return ".".join(reversed(parts))
        return ""

    def _arg_contains_taint(self, node: ast.Call) -> bool:
        """Check if any argument to a call originates from a taint source."""
        for arg in node.args:
            if isinstance(arg, ast.Name) and (arg.id in _TAINT_SOURCES or arg.id in self._tainted):
                return True
        for kw in node.keywords:
            if isinstance(kw.value, ast.Name) and (
                kw.value.id in _TAINT_SOURCES or kw.value.id in self._tainted
            ):
                return True
        return False

    # ------------------------------------------------------------------
    # Visitor methods
    # ------------------------------------------------------------------

    def visit_If(self, node: ast.If) -> None:
        """Detect hardcoded True/False conditions on auth-sensitive guards."""
        test = node.test

        # AUTH001 — if True: (always-true bypass)
        if self._is_literal_true(test):
            self._add(
                Severity.CRITICAL,
                "AUTH001",
                "Hardcoded 'if True:' — unconditional execution bypass detected.",
                node,
            )

        # AUTH002 — if False: (dead code removal of security guard)
        elif self._is_literal_false(test):
            self._add(
                Severity.HIGH,
                "AUTH002",
                "Hardcoded 'if False:' — security guard may be permanently disabled.",
                node,
            )

        # AUTH003 — if not <auth_name>: pattern reversal
        elif isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
            name = self._name_of(test.operand)
            if name and name.lower() in _AUTH_NAMES:
                self._add(
                    Severity.CRITICAL,
                    "AUTH003",
                    f"Inverted auth guard: 'if not {name}:' — permission logic may be reversed.",
                    node,
                )

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        """Detect privilege escalation and hardcoded secret assignments."""
        for target in node.targets:
            name = self._name_of(target)
            if name is None:
                continue

            name_lower = name.lower()

            # PRIV001 — is_admin = True (direct privilege escalation)
            if name_lower in _AUTH_NAMES and self._is_literal_true(node.value):
                self._add(
                    Severity.CRITICAL,
                    "PRIV001",
                    f"Privilege escalation: '{name} = True' — hardcoded permission grant detected.",
                    node,
                )

            # PRIV002 — role = "admin" (hardcoded role assignment)
            elif name_lower in _AUTH_NAMES and self._is_nonempty_string(node.value):
                value = node.value.s if hasattr(node.value, "s") else node.value.value
                if any(
                    priv in str(value).lower()
                    for priv in ("admin", "superuser", "root", "staff", "god")
                ):
                    self._add(
                        Severity.CRITICAL,
                        "PRIV002",
                        f"Hardcoded privileged role: '{name} = {value!r}'.",
                        node,
                    )

            # SEC001 — hardcoded secret value
            elif name_lower in _SECRET_NAMES and self._is_nonempty_string(node.value):
                self._add(
                    Severity.CRITICAL,
                    "SEC001",
                    f"Hardcoded secret: '{name}' assigned a literal string value. "
                    "Secrets must come from environment variables or a vault.",
                    node,
                )

            # Taint propagation — track assignments from taint sources
            if isinstance(node.value, ast.Name) and node.value.id in _TAINT_SOURCES:
                if name:
                    self._tainted.add(name)

        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        """Detect augmented assignments on auth fields (e.g. permissions |= ADMIN)."""
        name = self._name_of(node.target)
        if name and name.lower() in _AUTH_NAMES:
            self._add(
                Severity.HIGH,
                "PRIV003",
                f"Augmented assignment on security field '{name}' — "
                "verify this does not grant unintended privileges.",
                node,
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Detect dangerous sink calls and tainted argument flows."""
        call_name = self._call_name(node)

        # TAINT001 — taint source flowing into dangerous sink
        if call_name in _TAINT_SINKS and self._arg_contains_taint(node):
            self._add(
                Severity.CRITICAL,
                "TAINT001",
                f"Taint flow: user-controlled input reaches dangerous sink "
                f"'{call_name}'. Potential injection vulnerability.",
                node,
            )

        # TAINT002 — dangerous sink called without obvious sanitization
        elif call_name in _TAINT_SINKS:
            self._add(
                Severity.HIGH,
                "TAINT002",
                f"Dangerous function call: '{call_name}' — "
                "verify all arguments are sanitized before use.",
                node,
            )

        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        """Detect weakened comparisons on auth values."""
        left_name = self._name_of(node.left)
        if left_name and left_name.lower() in _AUTH_NAMES:
            for op, comparator in zip(node.ops, node.comparators):
                # AUTH004 — auth_field is True (identity instead of equality)
                if isinstance(op, ast.Is) and self._is_literal_true(comparator):
                    self._add(
                        Severity.MEDIUM,
                        "AUTH004",
                        f"Identity comparison '{left_name} is True' — "
                        "use explicit boolean checks for security conditions.",
                        node,
                    )
                # AUTH005 — auth_field == 0 / "" (falsy bypass)
                elif isinstance(op, ast.Eq) and isinstance(comparator, ast.Constant):
                    if comparator.value in (0, "", None, False):
                        self._add(
                            Severity.HIGH,
                            "AUTH005",
                            f"Auth field '{left_name}' compared to falsy value "
                            f"'{comparator.value!r}' — potential bypass.",
                            node,
                        )
        self.generic_visit(node)

    def visit_Delete(self, node: ast.Delete) -> None:
        """Detect deletion of security-sensitive attributes."""
        for target in node.targets:
            name = self._name_of(target)
            if name and name.lower() in _AUTH_NAMES | _SECRET_NAMES:
                self._add(
                    Severity.HIGH,
                    "SEC002",
                    f"Deletion of security-sensitive attribute '{name}' detected.",
                    node,
                )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Detect security decorator removal patterns."""
        # Look for functions named like auth guards with no decorators
        name_lower = node.name.lower()
        is_auth_func = any(
            kw in name_lower
            for kw in (
                "auth",
                "permission",
                "login_required",
                "require",
                "check_access",
                "verify",
                "validate_token",
            )
        )
        if is_auth_func and not node.decorator_list:
            # Only flag if the body is trivially bypassed
            body = node.body
            if len(body) == 1:
                stmt = body[0]
                # def require_auth(): return True
                if (
                    isinstance(stmt, ast.Return)
                    and stmt.value is not None
                    and self._is_literal_true(stmt.value)
                ):
                    self._add(
                        Severity.CRITICAL,
                        "AUTH006",
                        f"Security function '{node.name}' always returns True — "
                        "authentication/authorization completely bypassed.",
                        node,
                    )
                # def require_auth(): pass
                elif isinstance(stmt, ast.Pass):
                    self._add(
                        Severity.HIGH,
                        "AUTH007",
                        f"Security function '{node.name}' is a no-op (pass only) — "
                        "verify this is intentional.",
                        node,
                    )
        self.generic_visit(node)

    # Also handle async def
    visit_AsyncFunctionDef = visit_FunctionDef


# ---------------------------------------------------------------------------
# Patch parser — extract added lines from unified diff
# ---------------------------------------------------------------------------

_DIFF_ADDED_RE = re.compile(r"^\+(?!\+\+)")  # lines starting with + but not +++


def _extract_added_lines(patch: str) -> tuple[str, int]:
    """Extract lines added by the patch (+ prefix) as a single source string.

    Returns (source_code, line_count).
    The returned source is re-numbered starting from 1 so AST line numbers
    are meaningful relative to the added block.
    """
    added: list[str] = []
    for line in patch.splitlines():
        if _DIFF_ADDED_RE.match(line):
            added.append(line[1:])  # strip leading +
    source = "\n".join(added)
    return source, len(added)


def _try_parse(source: str) -> tuple[ast.Module | None, str | None]:
    """Attempt to parse source; return (tree, None) or (None, error_msg)."""
    try:
        tree = ast.parse(source)
        return tree, None
    except SyntaxError as exc:
        return None, f"SyntaxError at line {exc.lineno}: {exc.msg}"
    except Exception as exc:  # noqa: BLE001
        return None, f"Parse error: {exc}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class PatchSemanticValidator:
    """Validate a unified-diff patch for semantic security issues.

    Usage
    -----
    ::

        validator = PatchSemanticValidator()
        result = validator.validate(patch_text)

        if result.has_critical:
            # → BLOCK
        elif result.has_high:
            # → REVIEW
        else:
            # → proceed
    """

    def validate(self, patch: str) -> SemanticResult:
        """Analyse added lines in *patch* for security violations.

        Parameters
        ----------
        patch:
            Raw unified-diff string (as returned by the LLM).

        Returns
        -------
        SemanticResult
            Contains all violations found, parse errors, and line count.
        """
        result = SemanticResult()

        if not patch or not patch.strip():
            return result

        source, line_count = _extract_added_lines(patch)
        result.analysed_lines = line_count

        if not source.strip():
            # Patch is deletions only — no added code to analyse.
            return result

        # Attempt to dedent in case indented code was extracted.
        source = textwrap.dedent(source)

        tree, parse_error = _try_parse(source)

        if parse_error:
            # Partial analysis — log the error but still run regex fallback.
            result.parse_errors.append(parse_error)
            logger.debug("[SemanticValidator] Parse failed: %s", parse_error)
            self._regex_fallback(patch, result)
            return result

        visitor = _SecurityVisitor()
        visitor.visit(tree)
        result.violations.extend(visitor.violations)

        logger.info(
            "[SemanticValidator] Analysed %d lines — %d violation(s) found.",
            line_count,
            len(result.violations),
        )
        return result

    # ------------------------------------------------------------------
    # Regex fallback — catches obvious patterns when AST parse fails
    # ------------------------------------------------------------------

    _FALLBACK_PATTERNS: list[tuple[re.Pattern[str], Severity, str, str]] = [
        (
            re.compile(r"\bif\s+True\s*:", re.IGNORECASE),
            Severity.CRITICAL,
            "AUTH001",
            "Hardcoded 'if True:' detected (regex fallback — AST unavailable).",
        ),
        (
            re.compile(r"\bis_admin\s*=\s*True\b"),
            Severity.CRITICAL,
            "PRIV001",
            "is_admin = True detected (regex fallback).",
        ),
        (
            re.compile(r"\bpassword\s*=\s*['\"].+['\"]"),
            Severity.CRITICAL,
            "SEC001",
            "Hardcoded password literal detected (regex fallback).",
        ),
        (
            re.compile(r"\btoken\s*=\s*['\"].+['\"]"),
            Severity.CRITICAL,
            "SEC001",
            "Hardcoded token literal detected (regex fallback).",
        ),
        (
            re.compile(r"\beval\s*\("),
            Severity.HIGH,
            "TAINT002",
            "eval() call detected (regex fallback).",
        ),
        (
            re.compile(r"\bexec\s*\("),
            Severity.HIGH,
            "TAINT002",
            "exec() call detected (regex fallback).",
        ),
    ]

    def _regex_fallback(self, patch: str, result: SemanticResult) -> None:
        """Run regex-based checks when AST parsing fails."""
        added_lines = [line[1:] for line in patch.splitlines() if _DIFF_ADDED_RE.match(line)]
        for i, line in enumerate(added_lines, start=1):
            for pattern, severity, code, message in self._FALLBACK_PATTERNS:
                if pattern.search(line):
                    result.violations.append(
                        SemanticViolation(
                            severity=severity,
                            code=code,
                            message=message,
                            line=i,
                        )
                    )
