"""D1 — Patch Semantic Validator.

Performs AST-level static analysis on AI-proposed Python patches before
they reach the policy gate.  Pure ``ast`` module — no third-party deps,
no subprocess, no I/O.

Rule sets
---------
AUTH   — authentication / authorisation bypass patterns
PRIV   — privilege escalation (os, subprocess, file-system abuse)
SEC    — secrets / crypto misuse
TAINT  — untrusted data flowing into dangerous sinks

Severity model
--------------
CRITICAL  → automatic BLOCK  (mapped in policy_engine.py)
HIGH      → automatic REVIEW
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
# Severity + Violation
# ---------------------------------------------------------------------------


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class SemanticViolation:
    """One detected policy violation."""

    code: str  # e.g. "AUTH001"
    message: str  # human-readable description
    severity: Severity
    lineno: int  # 1-based, best-effort
    col_offset: int = 0
    rule_set: str = ""  # AUTH | PRIV | SEC | TAINT

    def __str__(self) -> str:
        return f"[{self.code}] line {self.lineno}: {self.message}"


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------


@dataclass
class SemanticValidationResult:
    """Aggregated result returned to the policy engine."""

    violations: list[SemanticViolation] = field(default_factory=list)
    parse_error: str | None = None  # set when AST parse itself fails

    # ------------------------------------------------------------------
    # Convenience filters (policy_engine.py uses these)
    # ------------------------------------------------------------------

    @property
    def critical_violations(self) -> list[SemanticViolation]:
        return [v for v in self.violations if v.severity is Severity.CRITICAL]

    @property
    def high_violations(self) -> list[SemanticViolation]:
        return [v for v in self.violations if v.severity is Severity.HIGH]

    @property
    def has_critical(self) -> bool:
        return bool(self.critical_violations)

    @property
    def has_high(self) -> bool:
        return bool(self.high_violations)

    @property
    def is_clean(self) -> bool:
        return not self.violations and self.parse_error is None

    def __len__(self) -> int:
        return len(self.violations)


# ---------------------------------------------------------------------------
# Base rule
# ---------------------------------------------------------------------------


class _Rule(ast.NodeVisitor):
    """Base class for all D1 rules.

    Each subclass implements visit_* methods and appends to
    ``self._violations``.  Call ``run(tree)`` to execute.
    """

    rule_set: str = ""

    def __init__(self) -> None:
        self._violations: list[SemanticViolation] = []

    def run(self, tree: ast.AST) -> list[SemanticViolation]:
        self.visit(tree)
        return list(self._violations)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _name(node: ast.expr) -> str:
        """Best-effort string representation of a call target."""
        if isinstance(node, ast.Attribute):
            return f"{_Rule._name(node.value)}.{node.attr}"
        if isinstance(node, ast.Name):
            return node.id
        return ""

    @staticmethod
    def _str_value(node: ast.expr) -> str | None:
        """Return the string value of a Constant node, else None."""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        return None

    def _add(
        self,
        code: str,
        message: str,
        severity: Severity,
        node: ast.AST,
    ) -> None:
        self._violations.append(
            SemanticViolation(
                code=code,
                message=message,
                severity=severity,
                lineno=getattr(node, "lineno", 0),
                col_offset=getattr(node, "col_offset", 0),
                rule_set=self.rule_set,
            )
        )


# ===========================================================================
# AUTH rule set
# ===========================================================================


class _AuthRules(_Rule):
    """AUTH — authentication / authorisation bypass detection."""

    rule_set = "AUTH"

    # Calls that unconditionally disable auth checks
    _DISABLED_AUTH_CALLS: frozenset[str] = frozenset(
        {
            # Flask-Login / Django decorators removed at call sites
            "login_required",
            "permission_required",
            "require_http_methods",
            # Django REST Framework
            "IsAuthenticated",
            "IsAdminUser",
            # JWT helpers
            "jwt_required",
            "verify_jwt_in_request",
            # Generic
            "check_auth",
            "authenticate",
            "authorize",
            "require_role",
        }
    )

    # Keyword argument names that are used to bypass auth
    _BYPASS_KWARGS: frozenset[str] = frozenset(
        {
            "skip_auth",
            "bypass_auth",
            "disable_auth",
            "no_auth",
            "unauthenticated",
            "anonymous",
        }
    )

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        name = self._name(node.func)

        # AUTH001 — dangerous bypass kwargs set to True
        for kw in node.keywords:
            if kw.arg in self._BYPASS_KWARGS:
                # flag when explicitly True or truthy non-False constant
                if isinstance(kw.value, ast.Constant) and kw.value.value not in (False, 0, None):
                    self._add(
                        "AUTH001",
                        f"Potentially disabling auth check via kwarg '{kw.arg}=True'",
                        Severity.CRITICAL,
                        node,
                    )

        # AUTH002 — hardcoded credentials passed to auth calls
        for arg in node.args:
            s = self._str_value(arg)
            if s and _looks_like_hardcoded_credential(s):
                self._add(
                    "AUTH002",
                    f"Hardcoded credential string passed to '{name}()'",
                    Severity.CRITICAL,
                    node,
                )

        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:  # noqa: N802
        # AUTH003 — `if password == "hardcoded"` style comparisons
        for comparator in node.comparators:
            s = self._str_value(comparator)
            if s and _looks_like_hardcoded_credential(s):
                self._add(
                    "AUTH003",
                    "Hardcoded credential used in comparison — timing-safe compare required",
                    Severity.HIGH,
                    node,
                )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._check_decorator_removal(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._check_decorator_removal(node)
        self.generic_visit(node)

    def _check_decorator_removal(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        # AUTH004 — function has no auth decorators but its name strongly
        # implies it is a protected endpoint
        _PROTECTED_NAMES = ("admin", "dashboard", "settings", "profile", "account")
        if any(kw in node.name.lower() for kw in _PROTECTED_NAMES):
            decorator_names = {self._name(d) for d in node.decorator_list}
            if not decorator_names.intersection(self._DISABLED_AUTH_CALLS):
                # Only flag if there are NO decorators at all — a patch that
                # strips all decorators from a protected endpoint is suspicious.
                if not node.decorator_list:
                    self._add(
                        "AUTH004",
                        f"Protected-looking endpoint '{node.name}' has no auth decorator",
                        Severity.HIGH,
                        node,
                    )


# ===========================================================================
# PRIV rule set
# ===========================================================================


class _PrivRules(_Rule):
    """PRIV — privilege escalation and dangerous system-level access."""

    rule_set = "PRIV"

    # (module_or_attr_prefix, severity, code, message)
    _DANGEROUS_CALLS: tuple[tuple[str, Severity, str, str], ...] = (
        # subprocess / shell execution
        (
            "subprocess.call",
            Severity.CRITICAL,
            "PRIV001",
            "subprocess.call() with shell=True allows arbitrary code execution",
        ),
        (
            "subprocess.run",
            Severity.HIGH,
            "PRIV002",
            "subprocess.run() — verify no user-controlled input reaches this call",
        ),
        (
            "subprocess.Popen",
            Severity.HIGH,
            "PRIV003",
            "subprocess.Popen() — verify no user-controlled input reaches this call",
        ),
        (
            "subprocess.check_output",
            Severity.HIGH,
            "PRIV004",
            "subprocess.check_output() — verify no user-controlled input reaches this call",
        ),
        (
            "os.system",
            Severity.CRITICAL,
            "PRIV005",
            "os.system() executes shell commands — severe injection risk",
        ),
        (
            "os.popen",
            Severity.CRITICAL,
            "PRIV006",
            "os.popen() executes shell commands — use subprocess instead",
        ),
        (
            "os.execv",
            Severity.CRITICAL,
            "PRIV007",
            "os.execv() replaces the current process — extremely dangerous",
        ),
        (
            "os.execve",
            Severity.CRITICAL,
            "PRIV008",
            "os.execve() replaces the current process — extremely dangerous",
        ),
        # privilege bits
        (
            "os.chmod",
            Severity.HIGH,
            "PRIV009",
            "os.chmod() — verify no world-writable bits (0o777) are set",
        ),
        (
            "os.chown",
            Severity.HIGH,
            "PRIV010",
            "os.chown() — changing file ownership may escalate privileges",
        ),
        (
            "os.setuid",
            Severity.CRITICAL,
            "PRIV011",
            "os.setuid() changes process UID — privilege escalation risk",
        ),
        (
            "os.setgid",
            Severity.CRITICAL,
            "PRIV012",
            "os.setgid() changes process GID — privilege escalation risk",
        ),
        # dynamic code execution
        (
            "eval",
            Severity.CRITICAL,
            "PRIV013",
            "eval() executes arbitrary code — never pass user input",
        ),
        (
            "exec",
            Severity.CRITICAL,
            "PRIV014",
            "exec() executes arbitrary code — never pass user input",
        ),
        (
            "compile",
            Severity.HIGH,
            "PRIV015",
            "compile() + exec pattern — verify source is trusted",
        ),
        (
            "__import__",
            Severity.HIGH,
            "PRIV016",
            "__import__() dynamic import — verify module name is not user-controlled",
        ),
        (
            "importlib.import_module",
            Severity.HIGH,
            "PRIV017",
            "importlib.import_module() — verify module name is not user-controlled",
        ),
        # pickle / deserialization
        (
            "pickle.loads",
            Severity.CRITICAL,
            "PRIV018",
            "pickle.loads() on untrusted data allows arbitrary code execution",
        ),
        (
            "pickle.load",
            Severity.CRITICAL,
            "PRIV019",
            "pickle.load() on untrusted data allows arbitrary code execution",
        ),
        (
            "marshal.loads",
            Severity.CRITICAL,
            "PRIV020",
            "marshal.loads() deserializes bytecode — only trust signed sources",
        ),
        (
            "yaml.load",
            Severity.CRITICAL,
            "PRIV021",
            "yaml.load() without Loader=yaml.SafeLoader allows code execution",
        ),
        # temp file abuse
        (
            "tempfile.mktemp",
            Severity.HIGH,
            "PRIV022",
            "tempfile.mktemp() is insecure (TOCTOU) — use mkstemp() or NamedTemporaryFile()",
        ),
    )

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        name = self._name(node.func)

        for prefix, severity, code, message in self._DANGEROUS_CALLS:
            # Match exact full name OR bare function name — but require the
            # bare suffix to be the *entire* local name (e.g. "load" must not
            # match both "pickle.load" and "yaml.load" for the same call).
            bare = prefix.split(".")[-1]
            module = prefix.split(".")[0] if "." in prefix else ""
            full_match = name == prefix
            bare_match = name == bare or (
                name.endswith(f".{bare}") and (not module or name.startswith(module))
            )
            if full_match or bare_match:
                # subprocess with shell=True → CRITICAL, without → HIGH
                _subprocess_calls = (
                    "subprocess.run",
                    "subprocess.Popen",
                    "subprocess.call",
                    "subprocess.check_output",
                )
                if prefix in _subprocess_calls:
                    shell_true = any(
                        kw.arg == "shell"
                        and isinstance(kw.value, ast.Constant)
                        and kw.value.value is True
                        for kw in node.keywords
                    )
                    effective_severity = Severity.CRITICAL if shell_true else severity
                    effective_message = (
                        message.replace("— verify", "with shell=True — arbitrary code execution")
                        if shell_true
                        else message
                    )
                    self._add(code, effective_message, effective_severity, node)
                else:
                    self._add(code, message, severity, node)
                break

        # PRIV023 — world-writable chmod literal
        if name in ("os.chmod", "chmod"):
            for arg in node.args[1:2]:  # second positional arg is mode
                if isinstance(arg, ast.Constant) and isinstance(arg.value, int):
                    if arg.value & 0o002:  # world-writable bit
                        self._add(
                            "PRIV023",
                            f"os.chmod() sets world-writable bit (mode=0o{arg.value:o})",
                            Severity.CRITICAL,
                            node,
                        )

        self.generic_visit(node)


# ===========================================================================
# SEC rule set
# ===========================================================================


class _SecRules(_Rule):
    """SEC — secrets and cryptographic misuse."""

    rule_set = "SEC"

    # Weak / broken algorithms
    _WEAK_ALGOS: frozenset[str] = frozenset({"md5", "sha1", "sha-1", "des", "rc4", "rc2"})

    # Assignment targets that suggest secret storage in plain text
    _SECRET_VAR_NAMES: frozenset[str] = frozenset(
        {
            "password",
            "passwd",
            "pwd",
            "secret",
            "secret_key",
            "api_key",
            "apikey",
            "token",
            "auth_token",
            "access_token",
            "private_key",
            "signing_key",
        }
    )

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        name = self._name(node.func).lower()

        # SEC001 — weak hash algorithm
        if "hashlib" in name or name in ("md5", "sha1"):
            for arg in node.args:
                algo = self._str_value(arg)
                if algo and algo.lower().replace("-", "") in {
                    a.replace("-", "") for a in self._WEAK_ALGOS
                }:
                    self._add(
                        "SEC001",
                        f"Weak hash algorithm '{algo}' — use SHA-256 or stronger",
                        Severity.HIGH,
                        node,
                    )
            # Direct call e.g. hashlib.md5(...)
            for algo in self._WEAK_ALGOS:
                if name.endswith(algo.replace("-", "")):
                    self._add(
                        "SEC001",
                        f"Weak hash algorithm '{algo}' — use SHA-256 or stronger",
                        Severity.HIGH,
                        node,
                    )

        # SEC002 — random used for security-sensitive purpose
        if name in (
            "random.random",
            "random.randint",
            "random.choice",
            "random.randrange",
            "random.uniform",
        ):
            self._add(
                "SEC002",
                f"'{name}' is not cryptographically secure — use secrets module",
                Severity.HIGH,
                node,
            )

        # SEC003 — ssl verification disabled
        if name in (
            "requests.get",
            "requests.post",
            "requests.put",
            "requests.delete",
            "requests.request",
            "requests.session",
        ):
            for kw in node.keywords:
                if kw.arg == "verify" and isinstance(kw.value, ast.Constant) and not kw.value.value:
                    self._add(
                        "SEC003",
                        "SSL verification disabled (verify=False) — MITM attack risk",
                        Severity.CRITICAL,
                        node,
                    )

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        # SEC004 — hardcoded secret assigned to a sensitive variable
        value_str = self._str_value(node.value)
        if value_str and _looks_like_hardcoded_credential(value_str):
            for target in node.targets:
                target_name = self._name(target).lower()
                if any(kw in target_name for kw in self._SECRET_VAR_NAMES):
                    self._add(
                        "SEC004",
                        (
                            f"Hardcoded secret assigned to '{self._name(target)}'"
                            " — use env vars or a vault"
                        ),
                        Severity.CRITICAL,
                        node,
                    )
        self.generic_visit(node)

    def visit_keyword(self, node: ast.keyword) -> None:  # noqa: N802
        # SEC005 — secret passed as keyword argument
        if node.arg and any(kw in node.arg.lower() for kw in self._SECRET_VAR_NAMES):
            s = self._str_value(node.value)
            if s and _looks_like_hardcoded_credential(s):
                self._add(
                    "SEC005",
                    f"Hardcoded secret in keyword argument '{node.arg}'",
                    Severity.CRITICAL,
                    node,
                )
        self.generic_visit(node)


# ===========================================================================
# TAINT rule set
# ===========================================================================


class _TaintRules(_Rule):
    """TAINT — untrusted data flowing into dangerous sinks.

    Lightweight single-pass taint: any name that originates from a
    *source* (request, user_input, environ) and is directly passed
    (without any sanitization call in between) to a *sink* is flagged.

    This is intentionally conservative — false negatives are acceptable,
    false positives are not, because every flag causes a REVIEW, not an
    auto-block.
    """

    rule_set = "TAINT"

    # Sources — call expressions whose return values carry taint
    _TAINT_SOURCES: frozenset[str] = frozenset(
        {
            # HTTP request objects (Flask / Django / FastAPI / Starlette)
            "request.args.get",
            "request.form.get",
            "request.json",
            "request.get_json",
            "request.data",
            "request.values.get",
            "request.cookies.get",
            "request.headers.get",
            # Django specifics
            "request.GET.get",
            "request.POST.get",
            # FastAPI / Pydantic body
            "Body",
            "Query",
            "Path",
            "Header",
            "Cookie",
            # Generic user / env input
            "input",
            "os.environ.get",
            "os.getenv",
            "sys.argv",
        }
    )

    # Sinks — call expressions that are dangerous when tainted
    _TAINT_SINKS: frozenset[str] = frozenset(
        {
            # SQL
            "execute",
            "cursor.execute",
            "db.execute",
            "session.execute",
            "connection.execute",
            "conn.execute",
            # Shell
            "os.system",
            "subprocess.call",
            "subprocess.run",
            "subprocess.Popen",
            "subprocess.check_output",
            "os.popen",
            # Template rendering
            "render_template_string",
            "jinja2.Template",
            "Template",
            "Markup",
            # Eval / exec
            "eval",
            "exec",
            # File ops
            "open",
            "Path",
            # HTTP redirect
            "redirect",
        }
    )

    def __init__(self) -> None:
        super().__init__()
        self._tainted: set[str] = set()

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        """Track assignments from taint sources."""
        if isinstance(node.value, ast.Call):
            src = self._name(node.value.func)
            in_sources = src in self._TAINT_SOURCES or any(
                node.value.func and src.endswith(s.split(".")[-1]) for s in self._TAINT_SOURCES
            )
            if in_sources:
                for target in node.targets:
                    tname = self._name(target)
                    if tname:
                        self._tainted.add(tname)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        """Flag tainted variables flowing into sinks."""
        sink = self._name(node.func)
        is_sink = sink in self._TAINT_SINKS or any(
            sink.endswith(f".{s.split('.')[-1]}") for s in self._TAINT_SINKS
        )
        if is_sink:
            for arg in node.args:
                arg_name = self._name(arg)
                if arg_name and arg_name in self._tainted:
                    self._add(
                        "TAINT001",
                        (
                            f"Untrusted input '{arg_name}' flows into"
                            f" sink '{sink}()' — sanitize before use"
                        ),
                        Severity.HIGH,
                        node,
                    )
            # Check string formatting / concatenation inside call args
            for arg in node.args:
                if isinstance(arg, (ast.JoinedStr, ast.BinOp)):
                    tainted_names = _extract_names(arg)
                    for tname in tainted_names:
                        if tname in self._tainted:
                            self._add(
                                "TAINT002",
                                (
                                    f"Untrusted input '{tname}' used in string"
                                    f" formatting passed to '{sink}()'"
                                    " — injection risk"
                                ),
                                Severity.CRITICAL,
                                node,
                            )
        self.generic_visit(node)


# ===========================================================================
# Helpers
# ===========================================================================


def _looks_like_hardcoded_credential(s: str) -> bool:
    """Heuristic: is this string a plausible hardcoded secret?

    Avoids flagging empty strings, placeholder text, SQL query strings,
    or very short values.
    """
    if len(s) < 8:
        return False
    # Obvious placeholders
    _PLACEHOLDERS = {
        "your-secret",
        "your_secret",
        "changeme",
        "change_me",
        "placeholder",
        "example",
        "test",
        "dummy",
        "password123",
        "secret123",
        "todo",
        "fixme",
    }
    if s.lower() in _PLACEHOLDERS or any(p in s.lower() for p in _PLACEHOLDERS):
        return False
    # SQL query strings — contain SQL keywords, not secrets
    _SQL_KEYWORDS = ("SELECT ", "INSERT ", "UPDATE ", "DELETE ", "WHERE ", "FROM ")
    if any(kw in s.upper() for kw in _SQL_KEYWORDS):
        return False
    # SQL parameter placeholders (%s, ?, :name) — not credentials
    if re.search(r"(%s|%d|\?|:\w+)", s):
        return False
    # Must contain at least one non-alpha character (keys, hashes, tokens do)
    has_special = any(c in s for c in "0123456789!@#$^&*-_=+/\\")
    return has_special


def _extract_names(node: ast.expr) -> list[str]:
    """Recursively extract all Name ids from an expression node."""
    names: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.append(child.id)
    return names


def _extract_added_lines(patch: str) -> str:
    """Return only lines added by the patch (lines starting with '+').

    Strips the leading '+' so the result is valid Python source.
    Ignores '+++' diff headers.
    """
    lines = []
    for line in patch.splitlines():
        if line.startswith("+++"):
            continue
        if line.startswith("+"):
            lines.append(line[1:])
    return "\n".join(lines)


# ===========================================================================
# Public API
# ===========================================================================


class PatchSemanticValidator:
    """Stateless AST validator — safe to share across threads.

    Usage::

        validator = PatchSemanticValidator()
        result = validator.validate(patch_text)
        if result.has_critical:
            raise PolicyViolation(result.critical_violations)
    """

    _RULES: tuple[type[_Rule], ...] = (
        _AuthRules,
        _PrivRules,
        _SecRules,
        _TaintRules,
    )

    def validate(self, patch: str) -> SemanticValidationResult:
        """Analyse *patch* and return a :class:`SemanticValidationResult`.

        The patch may be a unified diff or raw Python source — both are
        handled.  When a diff is provided, only the *added* lines are
        analysed (removed lines are safe by definition).
        """
        if not patch or not patch.strip():
            return SemanticValidationResult()

        # Determine source to parse
        is_diff = any(line.startswith(("---", "+++", "@@")) for line in patch.splitlines()[:10])
        source = _extract_added_lines(patch) if is_diff else patch

        if not source.strip():
            logger.debug("[D1] Patch has no added lines — nothing to validate")
            return SemanticValidationResult()

        # Dedent in case the patch is indented (e.g. inside a class)
        source = textwrap.dedent(source)

        # Parse
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            logger.warning("[D1] AST parse failed: %s", exc)
            return SemanticValidationResult(
                parse_error=f"SyntaxError at line {exc.lineno}: {exc.msg}"
            )

        # Run all rule sets
        all_violations: list[SemanticViolation] = []
        for rule_cls in self._RULES:
            rule = rule_cls()
            violations = rule.run(tree)
            all_violations.extend(violations)
            if violations:
                logger.debug(
                    "[D1] %s found %d violation(s)",
                    rule_cls.__name__,
                    len(violations),
                )

        result = SemanticValidationResult(violations=all_violations)

        if result.has_critical:
            logger.warning(
                "[D1] %d critical violation(s) — policy will BLOCK",
                len(result.critical_violations),
            )
        elif result.has_high:
            logger.info(
                "[D1] %d high violation(s) — policy will REVIEW",
                len(result.high_violations),
            )
        else:
            logger.debug("[D1] No violations found")

        return result
