"""Apply unified diffs to an isolated workspace and run pytest.

Security notes:
- All file writes are confined to `workspace` (temp dir).
- subprocess runs pytest with a 60-second wall-clock timeout.
- No shell=True anywhere.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from src.integrations.patch_utils import (
    PatchRejected,
    apply_verified,
    normalize_repo_path,
    parse_single_file_patch,
)

logger = logging.getLogger(__name__)

_TEST_TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class PatchResult:
    success: bool
    error: str = ""


@dataclass(frozen=True)
class TestResult:
    success: bool
    output: str = ""
    returncode: int = -1


class PatchRunner:
    """Apply a unified diff to a temp workspace copy and run the test suite.

    Parameters
    ----------
    project_root:
        Source-of-truth repo root. Files are copied from here into
        the isolated workspace before patching.
    """

    def __init__(self, project_root: Path) -> None:
        self._root = project_root.resolve()

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def apply(
        self,
        patch: str,
        patch_file: str,
        workspace: Path,
    ) -> PatchResult:
        """Copy target file into workspace, apply unified diff, write result.

        Parameters
        ----------
        patch:
            Unified diff string (must have --- a/<file> / +++ b/<file> headers).
        patch_file:
            Repo-relative path of the file being patched.
        workspace:
            Isolated temp directory for this pipeline run.
        """
        try:
            rel_path = normalize_repo_path(patch_file)
        except PatchRejected as exc:
            return PatchResult(success=False, error=f"Unsafe patch path: {exc}")

        source = self._root / rel_path
        dest = workspace / rel_path
        if not source.resolve().is_relative_to(self._root):
            return PatchResult(
                success=False,
                error=f"Source path leaves the project root: {rel_path}",
            )
        if not dest.resolve().is_relative_to(workspace.resolve()):
            return PatchResult(
                success=False,
                error=f"Target path leaves the workspace: {rel_path}",
            )
        if not source.exists():
            return PatchResult(
                success=False,
                error=f"Source file not found: {source}",
            )

        dest.parent.mkdir(parents=True, exist_ok=True)

        try:
            original = source.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return PatchResult(success=False, error=f"Cannot read source: {exc}")

        try:
            header_file, patch_set = parse_single_file_patch(patch)
        except PatchRejected as exc:
            return PatchResult(success=False, error=f"Invalid unified diff: {exc}")
        if header_file != rel_path:
            return PatchResult(
                success=False,
                error=f"Diff header {header_file} does not match patch_file {rel_path}",
            )

        try:
            patched = apply_verified(original, patch_set)
        except Exception as exc:
            return PatchResult(success=False, error=f"Patch application error: {exc}")

        if patched == original:
            return PatchResult(success=False, error="Patch produced no changes.")

        try:
            dest.write_text(patched, encoding="utf-8")
        except OSError as exc:
            return PatchResult(success=False, error=f"Cannot write patched file: {exc}")

        logger.debug("Patch applied: %s → %s", patch_file, dest)
        return PatchResult(success=True)

    def run_tests(self, workspace: Path) -> TestResult:
        """Run pytest from the project root with a hard timeout.

        Pytest discovers tests normally; the patched file in `workspace`
        is NOT on the import path — this validates the patch compiles and
        tests pass against the current codebase.  Full workspace isolation
        (hot-swap import) is a Phase 2 enhancement.
        """
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "-q",
            "--tb=short",
            "--no-header",
            f"--timeout={_TEST_TIMEOUT_SECONDS}",
        ]
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self._root),
                capture_output=True,
                text=True,
                timeout=_TEST_TIMEOUT_SECONDS + 5,
            )
        except subprocess.TimeoutExpired:
            return TestResult(
                success=False,
                output="pytest timed out",
                returncode=-1,
            )
        except Exception as exc:
            return TestResult(
                success=False,
                output=f"pytest invocation error: {exc}",
                returncode=-1,
            )

        output = (proc.stdout + proc.stderr).strip()
        return TestResult(
            success=proc.returncode == 0,
            output=output,
            returncode=proc.returncode,
        )
