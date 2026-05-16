"""
Fix production readiness:
1. vite.config.ts  - proxy ni dev-only, production hutumii proxy
2. api/client.ts   - baseURL inatoka VITE_API_URL env var (au relative / kwa prod)
3. .env.example    - kuonyesha jinsi ya configure
4. .env.local      - dev defaults (gitignored)
"""

from pathlib import Path

BASE = Path("frontend")

# ── vite.config.ts — add env-based API URL ───────────────────────────────
(BASE / "vite.config.ts").write_text(
    """\
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  return {
    plugins: [react()],
    resolve: {
      alias: { "@": path.resolve(__dirname, "./src") },
    },
    server: {
      port: 5173,
      // Dev proxy: only active during `npm run dev`
      // In production, VITE_API_URL points directly to the backend host.
      proxy: env.VITE_API_URL
        ? undefined
        : {
            "/api": {
              target: "http://localhost:8000",
              changeOrigin: true,
              rewrite: (p) => p.replace(/^\\/api/, ""),
            },
          },
    },
  };
});
""",
    encoding="utf-8",
)
print("WROTE  vite.config.ts")

# ── src/api/client.ts — dynamic baseURL ───────────────────────────────────
(BASE / "src/api/client.ts").write_text(
    """\
import axios from "axios";

/**
 * Base URL resolution:
 *  - Development (npm run dev):  proxy via Vite → localhost:8000
 *    VITE_API_URL is NOT set, so baseURL = "/api" (Vite rewrites to backend)
 *  - Production (npm run build): VITE_API_URL=https://your-backend.com
 *    baseURL = "https://your-backend.com" (direct, no proxy)
 *
 * Set in frontend/.env.local for dev overrides (gitignored).
 * Set in CI/CD or hosting platform env vars for production.
 */
const BASE_URL = import.meta.env.VITE_API_URL ?? "/api";

const getKey = () => localStorage.getItem("sentinai_api_key") ?? "";

export const http = axios.create({ baseURL: BASE_URL });

http.interceptors.request.use((cfg) => {
  const key = getKey();
  if (key) cfg.headers["X-API-Key"] = key;
  return cfg;
});

// ── Domain types (mirrors backend models) ─────────────────────────────────

export interface Incident {
  id: string;
  severity: "critical" | "high" | "medium" | "low";
  title: string;
  description: string;
  timestamp: string;
  status: "open" | "resolved";
  source?: string;
}

export interface Suggestion {
  patch_id: string;
  rule: string;
  confidence: number;
  explanation: string;
  diff: string;
  created_at?: string;
}

export interface StatsSnapshot {
  total_suggestions: number;
  total_fallbacks: number;
  fallback_rate: number;
  avg_latency_ms: number | null;
  p95_latency_ms: number | null;
  p99_latency_ms: number | null;
  latency_sample_count: number;
}

export interface ReadinessReport {
  status: "ok" | "degraded" | "fail";
  healthy: boolean;
  checks: Array<{
    name: string;
    status: "ok" | "degraded" | "fail";
    detail?: string;
    latency_ms?: number;
  }>;
}

// ── API surface ────────────────────────────────────────────────────────────

export const api = {
  health: {
    live:  () => http.get<{ status: string; service: string }>("/health/live"),
    ready: () => http.get<ReadinessReport>("/health/ready"),
  },
  stats:            () => http.get<StatsSnapshot>("/stats"),
  incidents:        () => http.get<Incident[]>("/incidents"),
  suggestions:      () => http.get<Suggestion[]>("/suggestions"),
  suggestionLatest: () => http.get<Suggestion>("/suggestions/latest"),
  scanNow:          () => http.post<{ detected_incidents: number }>("/scan-now"),
};
""",
    encoding="utf-8",
)
print("WROTE  src/api/client.ts")

# ── .env.example — document all env vars ──────────────────────────────────
(BASE / ".env.example").write_text(
    """\
# SentinAI Frontend — Environment Variables
# Copy to .env.local for local dev (never commit .env.local)

# Backend API base URL.
# Development: leave unset — Vite proxy handles routing to localhost:8000
# Production:  set to your deployed backend, e.g. https://api.sentinai.io
# VITE_API_URL=https://api.sentinai.io
""",
    encoding="utf-8",
)
print("WROTE  .env.example")

# ── .env.local — dev defaults (gitignored already via .gitignore pattern) ─
# Only write if it doesn't exist yet
env_local = BASE / ".env.local"
if not env_local.exists():
    env_local.write_text(
        """\
# Local dev overrides — gitignored, never commit this file
# Leave VITE_API_URL unset to use Vite proxy (recommended for dev)
# VITE_API_URL=http://localhost:8000
""",
        encoding="utf-8",
    )
    print("WROTE  .env.local")
else:
    print("SKIP   .env.local (already exists)")

print()
print("Done. Now run: npm run type-check")
