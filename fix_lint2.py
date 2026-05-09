"""
fix_lint2.py — Fix remaining ruff errors
Run from project root: python fix_lint2.py
"""

from pathlib import Path


def read(path):
    return Path(path).read_text(encoding="utf-8")


def write(path, content):
    Path(path).write_text(content, encoding="utf-8")
    print(f"  [FIXED] {path}")


# ─────────────────────────────────────────────────────────────
# Fix 1: conftest.py
#   E401 — Multiple imports on one line
#   E702 — Multiple statements on one line (semicolon)
#
#   Likely looks like: import os; import sys
#   or: import os, sys
# ─────────────────────────────────────────────────────────────
path = "conftest.py"
content = read(path)
print(f"conftest.py current content:\n{content}\n---")

lines = content.splitlines(keepends=True)
new_lines = []

for line in lines:
    stripped = line.strip()

    # Fix E702: split semicolon-separated statements into separate lines
    if ";" in stripped and not stripped.startswith("#"):
        parts = [p.strip() for p in stripped.split(";") if p.strip()]
        for part in parts:
            new_lines.append(part + "\n")
        continue

    # Fix E401: split comma-separated imports onto separate lines
    # e.g. "import os, sys" -> "import os\nimport sys"
    if stripped.startswith("import ") and "," in stripped:
        import_part = stripped[len("import ") :]
        modules = [m.strip() for m in import_part.split(",")]
        for mod in modules:
            new_lines.append(f"import {mod}\n")
        continue

    new_lines.append(line)

write(path, "".join(new_lines))


# ─────────────────────────────────────────────────────────────
# Fix 2: tests/test_m6_auto_patch.py line 255
#   F841 — `result` still unused (regex didn't catch the exact pattern)
#   Replace `result =` with `_result =` on that line
# ─────────────────────────────────────────────────────────────
path = "tests/test_m6_auto_patch.py"
content = read(path)
lines = content.splitlines(keepends=True)

target_line = lines[254]  # line 255 (0-indexed: 254)
print(f"Line 255 before fix: {target_line.rstrip()}")

if "result =" in target_line and "_result" not in target_line:
    lines[254] = target_line.replace("result =", "_result =", 1)
    print(f"Line 255 after fix:  {lines[254].rstrip()}")
    write(path, "".join(lines))
else:
    print(
        f"  [SKIP] line 255 already fixed or pattern not found: {target_line.rstrip()}"
    )


print("\nDone. Now run:")
print("  git add conftest.py tests/test_m6_auto_patch.py")
print('  git commit -m "fix: split conftest imports, fix unused result variable"')
print("  git push origin main")
