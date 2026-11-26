"""PR B: PatchRunner uses the shared patch helpers."""

from __future__ import annotations

from pathlib import Path

from src.services.patch_runner import PatchRunner

LINES = "".join(f"l{i}\n" for i in range(1, 21))


def _diff(path: str, *hunks: str, target: str | None = None) -> str:
    return f"--- a/{path}\n+++ b/{target or path}\n" + "".join(hunks)


def _setup(tmp_path: Path) -> tuple[Path, Path, PatchRunner]:
    root = tmp_path / "repo"
    root.mkdir()
    return root, tmp_path / "ws", PatchRunner(project_root=root)


def test_wrong_hunk_counts_still_apply_every_change(tmp_path: Path) -> None:
    root, ws, runner = _setup(tmp_path)
    (root / "x.py").write_text("a\nb\nc\nd\ne\n", encoding="utf-8")
    diff = _diff("x.py", "@@ -1,3 +1,3 @@\n a\n-b\n+B\n c\n-d\n+D\n e\n")
    result = runner.apply(diff, "x.py", ws)
    assert result.success, result.error
    assert (ws / "x.py").read_text(encoding="utf-8") == "a\nB\nc\nD\ne\n"


def test_wrong_line_number_is_found_by_content(tmp_path: Path) -> None:
    root, ws, runner = _setup(tmp_path)
    (root / "x.py").write_text(LINES, encoding="utf-8")
    diff = _diff("x.py", "@@ -1,3 +1,3 @@\n l9\n-l10\n+L10\n l11\n")
    result = runner.apply(diff, "x.py", ws)
    assert result.success, result.error
    assert (ws / "x.py").read_text(encoding="utf-8") == LINES.replace("l10\n", "L10\n")


def test_context_that_differs_from_the_file_is_rejected(tmp_path: Path) -> None:
    root, ws, runner = _setup(tmp_path)
    (root / "x.py").write_text("a = 1\n", encoding="utf-8")
    diff = _diff("x.py", "@@ -1,1 +1,1 @@\n-a = 9\n+a = 2\n")
    result = runner.apply(diff, "x.py", ws)
    assert not result.success
    assert "does not match" in result.error
    assert not (ws / "x.py").exists()


def test_patch_file_with_dot_dot_is_rejected_and_never_read(tmp_path: Path) -> None:
    root, ws, runner = _setup(tmp_path)
    (tmp_path / "outside.py").write_text("a = 1\n", encoding="utf-8")
    diff = _diff("outside.py", "@@ -1,1 +1,1 @@\n-a = 1\n+a = 2\n")
    result = runner.apply(diff, "../outside.py", ws)
    assert not result.success
    assert "Unsafe patch path" in result.error
    assert (tmp_path / "outside.py").read_text(encoding="utf-8") == "a = 1\n"


def test_patch_file_that_differs_from_the_diff_header_is_rejected(tmp_path: Path) -> None:
    root, ws, runner = _setup(tmp_path)
    (root / "x.py").write_text("a = 1\n", encoding="utf-8")
    (root / "y.py").write_text("a = 1\n", encoding="utf-8")
    diff = _diff("y.py", "@@ -1,1 +1,1 @@\n-a = 1\n+a = 2\n")
    result = runner.apply(diff, "x.py", ws)
    assert not result.success
    assert "does not match" in result.error
    assert not (ws / "x.py").exists()
    assert not (ws / "y.py").exists()


def test_diff_headers_naming_two_files_are_rejected(tmp_path: Path) -> None:
    root, ws, runner = _setup(tmp_path)
    (root / "x.py").write_text("a = 1\n", encoding="utf-8")
    diff = _diff("x.py", "@@ -1,1 +1,1 @@\n-a = 1\n+a = 2\n", target="y.py")
    result = runner.apply(diff, "x.py", ws)
    assert not result.success
    assert "Invalid unified diff" in result.error


def test_symlink_that_leaves_the_project_root_is_rejected(tmp_path: Path) -> None:
    root, ws, runner = _setup(tmp_path)
    (tmp_path / "secret.py").write_text("a = 1\n", encoding="utf-8")
    (root / "link.py").symlink_to(tmp_path / "secret.py")
    diff = _diff("link.py", "@@ -1,1 +1,1 @@\n-a = 1\n+a = 2\n")
    result = runner.apply(diff, "link.py", ws)
    assert not result.success
    assert "leaves the project root" in result.error
    assert (tmp_path / "secret.py").read_text(encoding="utf-8") == "a = 1\n"
