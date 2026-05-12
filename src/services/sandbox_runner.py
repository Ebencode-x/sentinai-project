"""Sandboxed Patch Runner — B1/B2.

B1: SandboxConfig — loads sentinai-sandbox.yml, builds docker run args.
B2: SandboxedPatchRunner — executes patches inside an ephemeral Docker
    container with network=none, read-only FS, CPU/memory limits.
    Falls back to PatchRunner when Docker is unavailable.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.services.patch_runner import PatchResult, PatchRunner, TestResult

logger = logging.getLogger(__name__)
_DEFAULT_CONFIG = Path(__file__).resolve().parent.parent.parent / "sentinai-sandbox.yml"


@dataclass
class SandboxConfig:
    """Parsed resource limits from sentinai-sandbox.yml."""

    image: str = "sentinai-sandbox:latest"
    network: str = "none"
    read_only_root: bool = True
    tmpfs_workspace: bool = True
    tmpfs_size_mb: int = 64
    memory_mb: int = 256
    cpus: float = 0.5
    timeout_seconds: int = 120
    user: str = "sentinai"
    workspace_mount: str = "/workspace"
    project_mount: str = "/app"
    security_opt: list[str] = field(default_factory=lambda: ["no-new-privileges"])
    drop_capabilities: list[str] = field(default_factory=lambda: ["ALL"])

    @classmethod
    def from_yaml(cls, path: Path = _DEFAULT_CONFIG) -> SandboxConfig:
        """Load config from sentinai-sandbox.yml. Falls back to defaults."""
        try:
            data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            sb = data.get("sandbox", {})
            res = sb.get("resources", {})
            return cls(
                image=sb.get("image", cls.image),
                network=sb.get("network", cls.network),
                read_only_root=sb.get("read_only_root", cls.read_only_root),
                tmpfs_workspace=sb.get("tmpfs_workspace", cls.tmpfs_workspace),
                tmpfs_size_mb=sb.get("tmpfs_size_mb", cls.tmpfs_size_mb),
                memory_mb=res.get("memory_mb", cls.memory_mb),
                cpus=res.get("cpus", cls.cpus),
                timeout_seconds=res.get("timeout_seconds", cls.timeout_seconds),
                user=sb.get("user", cls.user),
                workspace_mount=sb.get("workspace_mount", cls.workspace_mount),
                project_mount=sb.get("project_mount", cls.project_mount),
                security_opt=sb.get("security_opt", ["no-new-privileges"]),
                drop_capabilities=sb.get("drop_capabilities", ["ALL"]),
            )
        except FileNotFoundError:
            logger.warning("sentinai-sandbox.yml not found — using defaults")
            return cls()

    def to_docker_args(self) -> list[str]:
        """Build docker run flags from this config."""
        args = [
            "--rm",
            f"--network={self.network}",
            f"--memory={self.memory_mb}m",
            f"--cpus={self.cpus}",
            f"--user={self.user}",
        ]
        if self.read_only_root:
            args.append("--read-only")
        if self.tmpfs_workspace:
            args.append(f"--tmpfs={self.workspace_mount}:rw,size={self.tmpfs_size_mb}m")
        for opt in self.security_opt:
            args.extend(["--security-opt", opt])
        for cap in self.drop_capabilities:
            args.extend(["--cap-drop", cap])
        return args


class SandboxedPatchRunner:
    """Apply patches and run tests inside an ephemeral Docker container.

    B1: Config loading + interface.
    B2: Full Docker container execution with security constraints.

    Falls back to PatchRunner when Docker is unavailable so that
    local dev and CI-without-Docker environments still work.
    """

    def __init__(
        self,
        project_root: Path,
        config_path: Path = _DEFAULT_CONFIG,
    ) -> None:
        self._root = project_root.resolve()
        self.config = SandboxConfig.from_yaml(config_path)
        self._fallback = PatchRunner(project_root=self._root)
        self._docker_available = shutil.which("docker") is not None
        if not self._docker_available:
            logger.warning(
                "Docker not found — SandboxedPatchRunner will use "
                "PatchRunner fallback. Install Docker for full isolation."
            )

    # ------------------------------------------------------------------
    # Public API (mirrors PatchRunner)
    # ------------------------------------------------------------------

    def apply(self, patch: str, patch_file: str, workspace: Path) -> PatchResult:
        """Copy + patch file into workspace. Delegates to PatchRunner (host FS op)."""
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
        return self._run_in_container(workspace)

    # ------------------------------------------------------------------
    # Docker execution — B2 core
    # ------------------------------------------------------------------

    def _run_in_container(self, workspace: Path) -> TestResult:
        """Launch an ephemeral Docker container and run pytest inside it.

        Mount layout:
            /app        — read-only project source (host project root)
            /workspace  — rw tmpfs (patched file written here by apply())

        The container runs as non-root user `sentinai` (uid 10001).
        Network is disabled. Root FS is read-only. Resources are capped.
        """
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
        success = proc.returncode == 0
        logger.info("[Sandbox] Container exit=%s", proc.returncode)
        return TestResult(success=success, output=output, returncode=proc.returncode)

    def _build_docker_cmd(self, workspace: Path) -> list[str]:
        """Assemble the full docker run command."""
        args = self.config.to_docker_args()
        return [
            "docker",
            "run",
            *args,
            # Mount project root read-only
            "--volume",
            f"{self._root}:{self.config.project_mount}:ro",
            # Mount patched workspace read-write
            "--volume",
            f"{workspace.resolve()}:{self.config.workspace_mount}:rw",
            # Working directory inside container
            "--workdir",
            self.config.project_mount,
            # Image to run
            self.config.image,
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def docker_available(self) -> bool:
        return self._docker_available

    def docker_run_args(self) -> list[str]:
        """Return docker run flags for this config (used by B3 tests)."""
        return self.config.to_docker_args()

    def build_docker_cmd(self, workspace: Path) -> list[str]:
        """Public wrapper for _build_docker_cmd (used by tests)."""
        return self._build_docker_cmd(workspace)
