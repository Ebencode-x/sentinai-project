"""SandboxConfig — B1/B3. Shared config dataclass (no circular deps)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

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
