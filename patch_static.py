path = "src/main.py"
with open(path, "r") as f:
    content = f.read()

old_import = "from fastapi import FastAPI, Request, Response"
new_import = "from fastapi import FastAPI, Request, Response\nfrom fastapi.responses import FileResponse\nfrom fastapi.staticfiles import StaticFiles"
content = content.replace(old_import, new_import, 1)

spa_code = """

_frontend_dist = __import__("pathlib").Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=_frontend_dist / "assets"), name="assets")

    @app.get("/favicon.svg")
    async def favicon():
        return FileResponse(_frontend_dist / "favicon.svg")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        index = _frontend_dist / "index.html"
        return FileResponse(index)
"""

content = content.rstrip() + "\\n" + spa_code
with open(path, "w") as f:
    f.write(content)
print("Done!")
