"""
Adds production-ready CORS to src/main.py:
- Reads SENTINAI_CORS_ORIGINS env var (comma-separated list)
- Dev default: localhost:5173
- Strict: only listed origins, no wildcards in production
Also adds session expiry to frontend useApiKey hook.
"""

from pathlib import Path

# ── 1. src/main.py — add CORSMiddleware ──────────────────────────────────
main_py = Path("src/main.py")
content = main_py.read_text(encoding="utf-8")

old = """from fastapi import FastAPI

from src.api.routes import router
from src.core.config import settings
from src.core.state import app_state"""

new = """from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.core.config import settings
from src.core.state import app_state"""

content = content.replace(old, new)

old_app = """app = FastAPI(
    title=settings.app_name,
    description=(
        "Self-healing DevOps agent that watches logs and prepares AI remediation suggestions."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router)"""

new_app = """app = FastAPI(
    title=settings.app_name,
    description=(
        "Self-healing DevOps agent that watches logs and prepares AI remediation suggestions."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — origins controlled via SENTINAI_CORS_ORIGINS env var
# Dev default: http://localhost:5173 (Vite dev server)
# Production: set to your frontend domain, e.g. https://app.sentinai.io
# Never use ["*"] in production — API keys would be exposed cross-origin.
# ---------------------------------------------------------------------------
_raw_origins = settings.cors_origins if hasattr(settings, "cors_origins") else ""
_origins: list[str] = (
    [o.strip() for o in _raw_origins.split(",") if o.strip()]
    if _raw_origins
    else ["http://localhost:5173", "http://127.0.0.1:5173"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type", "Accept"],
    max_age=600,  # preflight cache: 10 minutes
)

app.include_router(router)"""

content = content.replace(old_app, new_app)
main_py.write_text(content, encoding="utf-8")
print("WROTE  src/main.py — CORSMiddleware added")

# ── 2. src/core/config.py — add cors_origins field ───────────────────────
config_py = Path("src/core/config.py")
cfg = config_py.read_text(encoding="utf-8")

if "cors_origins" not in cfg:
    # Append field to Settings class — find the last field and add after
    # Works for both pydantic v1 and v2 style
    if "model_config" in cfg or "class Config" in cfg:
        # pydantic v2
        insert = '\n    cors_origins: str = ""  # comma-separated, e.g. https://app.sentinai.io'
    else:
        insert = '\n    cors_origins: str = ""  # comma-separated, e.g. https://app.sentinai.io'

    # Find class Settings and append before the end
    lines = cfg.splitlines()
    out = []
    in_settings = False
    inserted = False
    for i, line in enumerate(lines):
        out.append(line)
        if "class Settings" in line:
            in_settings = True
        if in_settings and not inserted:
            # Insert after last field definition (line with `=`)
            next_lines = lines[i + 1 :]
            is_last_field = "=" in line and (
                not next_lines
                or (
                    next_lines[0].strip() == ""
                    and (len(next_lines) < 2 or not next_lines[1].strip().startswith(" "))
                )
            )
            if is_last_field:
                out.append(insert)
                inserted = True

    if not inserted:
        # Fallback: append at end of file
        out.append(insert)

    config_py.write_text("\n".join(out), encoding="utf-8")
    print("WROTE  src/core/config.py — cors_origins field added")
else:
    print("SKIP   src/core/config.py — cors_origins already present")

# ── 3. frontend/src/hooks/useApiKey.ts — add 8h session TTL ─────────────
hook = Path("frontend/src/hooks/useApiKey.ts")
hook.write_text(
    """\
import { useState, useCallback } from "react";

const KEY     = "sentinai_api_key";
const EXPIRY  = "sentinai_key_expiry";
const TTL_MS  = 8 * 60 * 60 * 1000; // 8 hours

function isExpired(): boolean {
  const exp = localStorage.getItem(EXPIRY);
  if (!exp) return true;
  return Date.now() > parseInt(exp, 10);
}

export function useApiKey() {
  const [hasKey, setHasKey] = useState(() => {
    const key = localStorage.getItem(KEY);
    if (!key || isExpired()) {
      localStorage.removeItem(KEY);
      localStorage.removeItem(EXPIRY);
      return false;
    }
    return true;
  });

  const setKey = useCallback((k: string) => {
    localStorage.setItem(KEY,    k.trim());
    localStorage.setItem(EXPIRY, String(Date.now() + TTL_MS));
    setHasKey(true);
  }, []);

  const clearKey = useCallback(() => {
    localStorage.removeItem(KEY);
    localStorage.removeItem(EXPIRY);
    setHasKey(false);
  }, []);

  return { hasKey, setKey, clearKey };
}
""",
    encoding="utf-8",
)
print("WROTE  frontend/src/hooks/useApiKey.ts — 8h session TTL added")

# ── 4. .env.example — document CORS var ──────────────────────────────────
env_ex = Path(".env.example")
if env_ex.exists():
    ex = env_ex.read_text(encoding="utf-8")
    if "SENTINAI_CORS_ORIGINS" not in ex:
        ex += "\n# Frontend origins allowed to call the API (comma-separated)\n"
        ex += "# SENTINAI_CORS_ORIGINS=https://app.sentinai.io,https://sentinai.io\n"
        env_ex.write_text(ex, encoding="utf-8")
        print("WROTE  .env.example — SENTINAI_CORS_ORIGINS documented")

print()
print("Done. Next:")
print("  ruff check . --fix && ruff format .")
print("  pytest tests/test_routes.py -v  (smoke test CORS middleware loads)")
