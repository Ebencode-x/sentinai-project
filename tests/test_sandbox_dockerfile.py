"""B1 tests — Dockerfile.sandbox structure and SandboxConfig."""

from __future__ import annotations

from pathlib import Path

import yaml

from src.services.sandbox_runner import SandboxConfig, SandboxedPatchRunner

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DOCKERFILE = _REPO_ROOT / "Dockerfile.sandbox"
_SANDBOX_YML = _REPO_ROOT / "sentinai-sandbox.yml"


class TestDockerfileStructure:
    def setup_method(self):
        self.content = _DOCKERFILE.read_text(encoding="utf-8")

    def test_dockerfile_exists(self):
        assert _DOCKERFILE.exists()

    def test_uses_python_311_slim(self):
        assert "FROM python:3.11-slim" in self.content

    def test_non_root_user_created(self):
        assert "useradd" in self.content and "sentinai" in self.content

    def test_user_switched_before_entrypoint(self):
        assert self.content.index("USER sentinai") < self.content.index("ENTRYPOINT")

    def test_network_none_documented(self):
        assert "--network none" in self.content

    def test_read_only_documented(self):
        assert "--read-only" in self.content

    def test_no_new_privileges_documented(self):
        assert "no-new-privileges" in self.content

    def test_memory_limit_documented(self):
        assert "--memory" in self.content

    def test_cpu_limit_documented(self):
        assert "--cpus" in self.content

    def test_workspace_dir_created(self):
        assert "mkdir -p /workspace" in self.content

    def test_workspace_owned_by_sentinai(self):
        assert "chown sentinai:sentinai /workspace" in self.content

    def test_entrypoint_runs_pytest(self):
        assert "pytest" in self.content

    def test_apt_cache_cleaned(self):
        assert "rm -rf /var/lib/apt/lists/*" in self.content

    def test_no_cache_pip_install(self):
        assert "--no-cache-dir" in self.content


class TestSandboxYml:
    def setup_method(self):
        self.sb = yaml.safe_load(_SANDBOX_YML.read_text(encoding="utf-8"))["sandbox"]

    def test_yml_exists(self):
        assert _SANDBOX_YML.exists()

    def test_network_is_none(self):
        assert self.sb["network"] == "none"

    def test_read_only_root_is_true(self):
        assert self.sb["read_only_root"] is True

    def test_memory_limit_present(self):
        assert self.sb["resources"]["memory_mb"] <= 512

    def test_cpu_limit_present(self):
        assert self.sb["resources"]["cpus"] <= 1.0

    def test_timeout_present(self):
        assert self.sb["resources"]["timeout_seconds"] > 0

    def test_user_is_sentinai(self):
        assert self.sb["user"] == "sentinai"

    def test_no_new_privileges_in_security_opt(self):
        assert "no-new-privileges" in self.sb["security_opt"]

    def test_drop_all_capabilities(self):
        assert "ALL" in self.sb["drop_capabilities"]


class TestSandboxConfig:
    def test_loads_from_yml(self):
        cfg = SandboxConfig.from_yaml(_SANDBOX_YML)
        assert cfg.network == "none"
        assert cfg.memory_mb <= 512
        assert cfg.cpus <= 1.0
        assert cfg.read_only_root is True

    def test_defaults_when_no_file(self, tmp_path):
        cfg = SandboxConfig.from_yaml(tmp_path / "missing.yml")
        assert cfg.network == "none"
        assert cfg.memory_mb == 256

    def test_to_docker_args_contains_network(self):
        assert "--network=none" in SandboxConfig().to_docker_args()

    def test_to_docker_args_contains_memory(self):
        assert "--memory=256m" in SandboxConfig(memory_mb=256).to_docker_args()

    def test_to_docker_args_contains_read_only(self):
        assert "--read-only" in SandboxConfig(read_only_root=True).to_docker_args()

    def test_to_docker_args_contains_user(self):
        assert "--user=sentinai" in SandboxConfig(user="sentinai").to_docker_args()

    def test_to_docker_args_contains_rm(self):
        assert "--rm" in SandboxConfig().to_docker_args()

    def test_to_docker_args_no_new_privileges(self):
        args = SandboxConfig(security_opt=["no-new-privileges"]).to_docker_args()
        assert "no-new-privileges" in args

    def test_to_docker_args_drop_capabilities(self):
        args = SandboxConfig(drop_capabilities=["ALL"]).to_docker_args()
        assert "--cap-drop" in args and "ALL" in args


class TestSandboxedPatchRunner:
    def test_instantiates(self, tmp_path):
        assert SandboxedPatchRunner(project_root=tmp_path) is not None

    def test_config_loaded(self, tmp_path):
        assert isinstance(SandboxedPatchRunner(project_root=tmp_path).config, SandboxConfig)

    def test_docker_available_is_bool(self, tmp_path):
        assert isinstance(SandboxedPatchRunner(project_root=tmp_path).docker_available, bool)

    def test_docker_run_args_returns_list(self, tmp_path):
        args = SandboxedPatchRunner(project_root=tmp_path).docker_run_args()
        assert isinstance(args, list) and len(args) > 0
