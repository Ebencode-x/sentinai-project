"""B2 tests — SandboxedPatchRunner Docker execution."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.services.patch_runner import TestResult
from src.services.sandbox_runner import SandboxedPatchRunner

_REPO_ROOT = Path(__file__).resolve().parent.parent


class TestBuildDockerCmd:
    def setup_method(self):
        self.runner = SandboxedPatchRunner(project_root=_REPO_ROOT)

    def test_cmd_starts_with_docker_run(self, tmp_path):
        cmd = self.runner.build_docker_cmd(tmp_path)
        assert cmd[0] == "docker"
        assert cmd[1] == "run"

    def test_cmd_contains_image(self, tmp_path):
        cmd = self.runner.build_docker_cmd(tmp_path)
        assert self.runner.config.image in cmd

    def test_cmd_contains_network_none(self, tmp_path):
        cmd = self.runner.build_docker_cmd(tmp_path)
        assert "--network=none" in cmd

    def test_cmd_contains_read_only(self, tmp_path):
        cmd = self.runner.build_docker_cmd(tmp_path)
        assert "--read-only" in cmd

    def test_cmd_contains_project_volume(self, tmp_path):
        cmd = self.runner.build_docker_cmd(tmp_path)
        volume_args = [cmd[i + 1] for i, a in enumerate(cmd) if a == "--volume"]
        assert any("/app:ro" in v for v in volume_args)

    def test_cmd_contains_workspace_volume(self, tmp_path):
        cmd = self.runner.build_docker_cmd(tmp_path)
        volume_args = [cmd[i + 1] for i, a in enumerate(cmd) if a == "--volume"]
        assert any("/workspace:rw" in v for v in volume_args)

    def test_cmd_contains_workdir(self, tmp_path):
        cmd = self.runner.build_docker_cmd(tmp_path)
        assert "--workdir" in cmd
        workdir_idx = cmd.index("--workdir")
        assert cmd[workdir_idx + 1] == "/app"

    def test_cmd_contains_rm(self, tmp_path):
        cmd = self.runner.build_docker_cmd(tmp_path)
        assert "--rm" in cmd

    def test_cmd_contains_memory(self, tmp_path):
        cmd = self.runner.build_docker_cmd(tmp_path)
        assert any("--memory=" in a for a in cmd)

    def test_cmd_contains_cpus(self, tmp_path):
        cmd = self.runner.build_docker_cmd(tmp_path)
        assert any("--cpus=" in a for a in cmd)

    def test_cmd_contains_user(self, tmp_path):
        cmd = self.runner.build_docker_cmd(tmp_path)
        assert any("--user=" in a for a in cmd)

    def test_cmd_contains_no_new_privileges(self, tmp_path):
        cmd = self.runner.build_docker_cmd(tmp_path)
        assert "no-new-privileges" in cmd

    def test_cmd_contains_cap_drop_all(self, tmp_path):
        cmd = self.runner.build_docker_cmd(tmp_path)
        assert "--cap-drop" in cmd
        cap_idx = cmd.index("--cap-drop")
        assert cmd[cap_idx + 1] == "ALL"


class TestRunInContainer:
    def setup_method(self):
        self.runner = SandboxedPatchRunner(project_root=_REPO_ROOT)

    def _mock_proc(self, returncode=0, stdout="1 passed", stderr=""):
        proc = MagicMock()
        proc.returncode = returncode
        proc.stdout = stdout
        proc.stderr = stderr
        return proc

    @patch("src.services.sandbox_runner.shutil.which", return_value="/usr/bin/docker")
    @patch("src.services.sandbox_runner.subprocess.run")
    def test_success_returns_true(self, mock_run, mock_which, tmp_path):
        mock_run.return_value = self._mock_proc(returncode=0, stdout="1 passed")
        runner = SandboxedPatchRunner(project_root=_REPO_ROOT)
        result = runner._run_in_container(tmp_path)
        assert result.success is True

    @patch("src.services.sandbox_runner.shutil.which", return_value="/usr/bin/docker")
    @patch("src.services.sandbox_runner.subprocess.run")
    def test_failure_returns_false(self, mock_run, mock_which, tmp_path):
        mock_run.return_value = self._mock_proc(returncode=1, stdout="1 failed")
        runner = SandboxedPatchRunner(project_root=_REPO_ROOT)
        result = runner._run_in_container(tmp_path)
        assert result.success is False

    @patch("src.services.sandbox_runner.shutil.which", return_value="/usr/bin/docker")
    @patch("src.services.sandbox_runner.subprocess.run")
    def test_output_captured(self, mock_run, mock_which, tmp_path):
        mock_run.return_value = self._mock_proc(returncode=0, stdout="5 passed", stderr="")
        runner = SandboxedPatchRunner(project_root=_REPO_ROOT)
        result = runner._run_in_container(tmp_path)
        assert "5 passed" in result.output

    @patch("src.services.sandbox_runner.shutil.which", return_value="/usr/bin/docker")
    @patch("src.services.sandbox_runner.subprocess.run", side_effect=TimeoutError)
    def test_timeout_returns_failure(self, mock_run, mock_which, tmp_path):
        runner = SandboxedPatchRunner(project_root=_REPO_ROOT)
        result = runner._run_in_container(tmp_path)
        assert result.success is False

    @patch("src.services.sandbox_runner.shutil.which", return_value="/usr/bin/docker")
    @patch("src.services.sandbox_runner.subprocess.run")
    def test_returncode_stored(self, mock_run, mock_which, tmp_path):
        mock_run.return_value = self._mock_proc(returncode=2)
        runner = SandboxedPatchRunner(project_root=_REPO_ROOT)
        result = runner._run_in_container(tmp_path)
        assert result.returncode == 2

    @patch("src.services.sandbox_runner.shutil.which", return_value=None)
    def test_run_tests_falls_back_when_no_docker(self, mock_which, tmp_path):
        runner = SandboxedPatchRunner(project_root=_REPO_ROOT)
        with patch.object(runner._fallback, "run_tests", return_value=TestResult(success=True)):
            result = runner.run_tests(tmp_path)
        assert result.success is True

    @patch("src.services.sandbox_runner.shutil.which", return_value="/usr/bin/docker")
    @patch("src.services.sandbox_runner.subprocess.run")
    def test_run_tests_uses_container_when_docker_available(self, mock_run, mock_which, tmp_path):
        mock_run.return_value = self._mock_proc(returncode=0)
        runner = SandboxedPatchRunner(project_root=_REPO_ROOT)
        result = runner.run_tests(tmp_path)
        assert mock_run.called
        assert result.success is True
