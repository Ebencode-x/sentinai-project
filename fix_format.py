"""
fix_format.py — Run ruff format on all Python files
Run from project root: python fix_format.py
"""

import subprocess
import sys

result = subprocess.run(
    [sys.executable, "-m", "ruff", "format", "."], capture_output=True, text=True
)

print(result.stdout)
if result.stderr:
    print(result.stderr)

if result.returncode == 0:
    print("All files formatted successfully.")
else:
    # ruff format may not be installed as module, try direct command
    result2 = subprocess.run(["ruff", "format", "."], capture_output=True, text=True)
    print(result2.stdout)
    if result2.stderr:
        print(result2.stderr)
