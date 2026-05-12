"""Sandboxed Patch Runner — B1/B2/B3."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from src.services.patch_runner import PatchResult, PatchRunner, TestResult
from src.services.resource_enforcer import ResourceLimitEnforcer
from src.services.sandbox_config import SandboxConfig

_DEFAULT_CONFIG = SandboxConfig.__dataclass_fields__  # noqa: F841 — kept for IDE nav
_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "sentinai-sandbox.yml"

logger = logging.getLogger(__name__)


class SandboxedPatchRunner:
    """Apply patches and run tests inside an ephemeral Docker container.

    B1: Config loading + interface.
    B2: Full Docker container execution with security constraints.
    B3: Resource limit enforcement before container launch.

    Falls back to PatchRunner when Docker is unavailable.
    """

    def __init__(
        self,
        project_root: Path,
        config_path: Path = _DEFAULT_CONFIG_PATH,
    ) -> None:
        self._root = project_root.resolve()
        self.config = SandboxConfig.from_yaml(config_path)
        self._fallback = PatchRunner(project_root=self._root)
        self._enforcer = ResourceLimitEnforcer()
        self._docker_available = shutil.which("docker") is not None
        if not self._docker_available:
            logger.warning(
                "Docker not found — SandboxedPatchRunner will use "
                "PatchRunner fallback. Install Docker for full isolation."
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def apply(self, patch: str, patch_file: str, workspace: Path) -> PatchResult:
        """Copy + patch file into workspace. Delegates to PatchRunner."""
        return self._fallback.apply(
            patch=patch,
            patch_file=patch_file,
            workspace=workspace,
        )

    def run_tests(self, workspace: Path) -> TestResult:
        """Run pytest inside Docker container if available, else host fallback."""
        if not self._docker_available:
            logger.warning("Docker unavailable — running tests on host (no isolation).")
            return self._fallback.run_tests(workspace=workspace)
        self._enforcer.enforce(self.config)
        return self._run_in_container(workspace)

    # ------------------------------------------------------------------
    # Docker execution — B2
    # ------------------------------------------------------------------

    def _run_in_container(self, workspace: Path) -> TestResult:
        """Launch an ephemeral Docker container and run pytest inside it."""
        cmd = self._build_docker_cmd(workspace)
        logger.info("[Sandbox] Running: %s", " ".join(cmd))
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout_seconds + 5,
            )
        except subprocess.TimeoutExpired:
            logger.error("[Sandbox] Container timed out after %ss", self.config.timeout_seconds)
            return TestResult(success=False, output="Sandbox container timed out.", returncode=-1)
        except Exception as exc:
            logger.error("[Sandbox] docker run failed: %s", exc)
            return TestResult(
                success=False,
                output=f"docker run invocation error: {exc}",
                returncode=-1,
            )
        output = (proc.stdout + proc.stderr).strip()
        logger.info("[Sandbox] Container exit=%s", proc.returncode)
        return TestResult(
            success=proc.returncode == 0,
            output=output,
            returncode=proc.returncode,
        )

    def _build_docker_cmd(self, workspace: Path) -> list[str]:
        """Assemble the full docker run command."""
        args = self.config.to_docker_args()
        return [
            "docker",
            "run",
            *args,
            "--volume",
            f"{self._root}:{self.config.project_mount}:ro",
            "--volume",
            f"{workspace.resolve()}:{self.config.workspace_mount}:rw",
            "--workdir",
            self.config.project_mount,
            self.config.image,
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def docker_available(self) -> bool:
        return self._docker_available

    def docker_run_args(self) -> list[str]:
        return self.config.to_docker_args()

    def build_docker_cmd(self, workspace: Path) -> list[str]:
        return self._build_docker_cmd(workspace)
