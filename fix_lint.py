"""
fix_lint.py — Fix all ruff lint errors in SentinAI
Run from project root: python fix_lint.py
"""

import re
from pathlib import Path


def read(path):
    return Path(path).read_text(encoding="utf-8")


def write(path, content):
    Path(path).write_text(content, encoding="utf-8")
    print(f"  [FIXED] {path}")


# ─────────────────────────────────────────────────────────────
# Fix 1: tests/test_watcher.py — remove unused `import pytest`
# ─────────────────────────────────────────────────────────────
path = "tests/test_watcher.py"
content = read(path)

# Remove standalone `import pytest` line if pytest not used directly
# (only used via decorators like @pytest.mark — check first)
if (
    "import pytest" in content
    and "@pytest." not in content
    and "pytest." not in content.replace("import pytest", "")
):
    content = re.sub(r"^import pytest\n", "", content, flags=re.MULTILINE)
    write(path, content)
else:
    print(f"  [SKIP] {path} — pytest may still be in use, check manually")


# ─────────────────────────────────────────────────────────────
# Fix 2: tests/test_m6_auto_patch.py
#   - remove unused `import pytest` (line 15)
#   - remove unused `from unittest.mock import PropertyMock` (line 13)
#   - fix unused variable `result` (line 256) → prefix with _
# ─────────────────────────────────────────────────────────────
path = "tests/test_m6_auto_patch.py"
content = read(path)

# Remove unused `import pytest` if not used as decorator/call
if (
    "import pytest" in content
    and "@pytest." not in content
    and "pytest." not in content.replace("import pytest", "")
):
    content = re.sub(r"^import pytest\n", "", content, flags=re.MULTILINE)
    print(f"  [FIXED] {path} — removed unused `import pytest`")

# Remove unused PropertyMock import
if "PropertyMock" in content:
    # Check if actually used somewhere other than the import line
    usage = [
        l for l in content.splitlines() if "PropertyMock" in l and "import" not in l
    ]
    if not usage:
        content = re.sub(r",\s*PropertyMock", "", content)
        content = re.sub(r"from unittest\.mock import PropertyMock\n", "", content)
        print(f"  [FIXED] {path} — removed unused `PropertyMock`")

# Fix unused variable `result` → `_result`
content = re.sub(
    r"(\s+)result = (mock_repo\.create_pull|pr_result)", r"\1_result = \2", content
)
print(f"  [FIXED] {path} — renamed unused `result` to `_result`")

write(path, content)


# ─────────────────────────────────────────────────────────────
# Fix 3: src/main.py — E402 module level import not at top
# ─────────────────────────────────────────────────────────────
path = "src/main.py"
if Path(path).exists():
    content = read(path)
    lines = content.splitlines(keepends=True)

    # Separate imports from non-import lines
    import_lines = []
    other_lines = []
    in_imports = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            import_lines.append(line)
        else:
            other_lines.append(line)

    # Only rewrite if there are mixed imports
    if import_lines and other_lines:
        # Find first non-blank, non-comment, non-import line
        # Put all imports at top (after any module docstring/comments)
        docstring_lines = []
        rest_lines = []
        past_docstring = False
        for line in other_lines:
            stripped = line.strip()
            if not past_docstring and (
                stripped == ""
                or stripped.startswith("#")
                or stripped.startswith('"""')
                or stripped.startswith("'''")
            ):
                docstring_lines.append(line)
            else:
                past_docstring = True
                rest_lines.append(line)

        new_content = "".join(docstring_lines + import_lines + rest_lines)
        write(path, new_content)
    else:
        print(f"  [SKIP] {path} — no E402 reorder needed")
else:
    print(f"  [SKIP] {path} — file not found")


print("\nDone. Now run:")
print("  git add tests/test_watcher.py tests/test_m6_auto_patch.py src/main.py")
print('  git commit -m "fix: resolve ruff lint errors (unused imports, E402)"')
print("  git push origin main")
