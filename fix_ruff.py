from pathlib import Path

# Add noqa to the scaffold files so ruff ignores them
# Better: add per-file-ignores in pyproject.toml

pyproject = Path("pyproject.toml")
content = pyproject.read_text(encoding="utf-8")

if "make_frontend.py" not in content:
    old = "[tool.ruff.lint]"
    new = """[tool.ruff.lint.per-file-ignores]
"make_frontend.py" = ["E501"]
"fix_prod.py" = ["E501"]
"fix_types.py" = ["E501"]

[tool.ruff.lint]"""
    content = content.replace(old, new)
    pyproject.write_text(content, encoding="utf-8")
    print("WROTE  pyproject.toml — added per-file-ignores for scaffold scripts")
else:
    print("SKIP   already patched")
