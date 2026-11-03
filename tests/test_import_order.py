import ast
import os
import subprocess
import sys


def test_bootstrap_is_first_src_import_in_main(request):
    source = (request.config.rootpath / "src" / "main.py").read_text()
    for node in ast.parse(source).body:
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        if any(name == "src" or name.startswith("src.") for name in names):
            assert names == ["src.bootstrap"]
            return
    raise AssertionError("no src import found in main.py")


def test_env_file_reaches_settings(request, tmp_path):
    env_file = tmp_path / "test.env"
    env_file.write_text("APP_NAME=FromEnvFile\n")
    env = {k: v for k, v in os.environ.items() if k != "APP_NAME"}
    env["SENTINAI_ENV_FILE"] = str(env_file)
    code = "import src.bootstrap\nfrom src.core.config import settings\nprint(settings.app_name)\n"
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=request.config.rootpath,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "FromEnvFile"
