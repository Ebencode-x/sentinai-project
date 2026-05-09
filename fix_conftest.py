"""
fix_conftest.py — Rewrite conftest.py correctly
Run from project root: python fix_conftest.py
"""

from pathlib import Path

content = "import sys\nimport os\nsys.path.insert(0, os.getcwd())\n"

Path("conftest.py").write_text(content, encoding="utf-8")
print("conftest.py rewritten to:")
print(content)
