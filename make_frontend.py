"""
Script ya kutengeneza frontend/ scaffold yote.
Run: python make_frontend.py  (kutoka root ya sentinai-project)
"""

from pathlib import Path

BASE = Path("frontend")

files = {}

# ── package.json ──────────────────────────────────────────────────────────
files["package.json"] = """{
  "name": "sentinai-ui",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint src --ext ts,tsx --max-warnings 0",
    "type-check": "tsc --noEmit"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.23.1",
    "axios": "^1.7.2",
    "@tanstack/react-query": "^5.45.1",
    "date-fns": "^3.6.0",
    "clsx": "^2.1.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@typescript-eslint/eslint-plugin": "^7.11.0",
    "@typescript-eslint/parser": "^7.11.0",
    "@vitejs/plugin-react": "^4.3.0",
    "autoprefixer": "^10.4.19",
    "eslint": "^8.57.0",
    "eslint-plugin-react-hooks": "^4.6.2",
    "eslint-plugin-react-refresh": "^0.4.7",
    "postcss": "^8.4.38",
    "tailwindcss": "^3.4.4",
    "typescript": "^5.4.5",
    "vite": "^5.2.12"
  }
}
"""

# ── vite.config.ts ────────────────────────────────────────────────────────
files["vite.config.ts"] = """import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\\/api/, ""),
      },
    },
  },
});
"""

# ── tsconfig.json ─────────────────────────────────────────────────────────
files["tsconfig.json"] = """{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
"""

# ── tsconfig.node.json ────────────────────────────────────────────────────
files["tsconfig.node.json"] = """{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
"""

# ── tailwind.config.ts ────────────────────────────────────────────────────
files["tailwind.config.ts"] = """import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        mono: ["'JetBrains Mono'", "'Fira Code'", "monospace"],
        display: ["'DM Mono'", "monospace"],
      },
      colors: {
        bg:      { DEFAULT: "#080c10", card: "#0d1117", border: "#1a2332" },
        accent:  { DEFAULT: "#00d4ff", dim: "#0099bb", glow: "#00d4ff33" },
        warn:    { DEFAULT: "#ff6b35", dim: "#cc4422" },
        ok:      { DEFAULT: "#00ff88", dim: "#00cc66" },
        muted:   "#4a5568",
        text:    { DEFAULT: "#c9d1d9", dim: "#8b949e" },
      },
      boxShadow: {
        "glow-accent": "0 0 20px #00d4ff33, 0 0 40px #00d4ff11",
        "glow-warn":   "0 0 20px #ff6b3533",
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4,0,0.6,1) infinite",
        "scan-line":  "scan 4s linear infinite",
        "fade-in":    "fadeIn 0.3s ease-out",
        "slide-up":   "slideUp 0.4s ease-out",
      },
      keyframes: {
        scan: {
          "0%":   { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100vh)" },
        },
        fadeIn: {
          from: { opacity: "0" },
          to:   { opacity: "1" },
        },
        slideUp: {
          from: { opacity: "0", transform: "translateY(12px)" },
          to:   { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
"""

# ── postcss.config.js ─────────────────────────────────────────────────────
files["postcss.config.js"] = """export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
"""

# ── index.html ────────────────────────────────────────────────────────────
files["index.html"] = """<!doctype html>
<html lang="en" class="dark">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>SentinAI — Security Operations</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&family=DM+Mono:ital,wght@0,300;0,400;0,500;1,300&display=swap"
      rel="stylesheet"
    />
  </head>
  <body class="bg-bg text-text font-mono">
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
"""

# ── public/favicon.svg ────────────────────────────────────────────────────
files["public/favicon.svg"] = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" fill="#080c10"/>
  <polygon points="16,4 28,10 28,22 16,28 4,22 4,10" fill="none" stroke="#00d4ff" stroke-width="2"/>
  <circle cx="16" cy="16" r="4" fill="#00d4ff"/>
</svg>
"""

# ── src/main.tsx ──────────────────────────────────────────────────────────
files["src/main.tsx"] = """import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 10_000,
      refetchOnWindowFocus: false,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>
);
"""

# ── src/index.css ─────────────────────────────────────────────────────────
files["src/index.css"] = """@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  * { box-sizing: border-box; margin: 0; padding: 0; }
  
  :root {
    --scrollbar-w: 6px;
    --scrollbar-track: #0d1117;
    --scrollbar-thumb: #1a2332;
  }

  body {
    background: #080c10;
    color: #c9d1d9;
    font-family: "JetBrains Mono", monospace;
    -webkit-font-smoothing: antialiased;
  }

  ::-webkit-scrollbar       { width: var(--scrollbar-w); }
  ::-webkit-scrollbar-track { background: var(--scrollbar-track); }
  ::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: #243044; }

  ::selection { background: #00d4ff22; color: #00d4ff; }
}

@layer utilities {
  .glow-text  { text-shadow: 0 0 20px #00d4ff88; }
  .glow-warn  { text-shadow: 0 0 20px #ff6b3588; }
  .glow-ok    { text-shadow: 0 0 20px #00ff8888; }
  .scanline   {
    background: linear-gradient(transparent 50%, #00000008 50%);
    background-size: 100% 4px;
    pointer-events: none;
  }
}
"""

# ── src/api/client.ts ─────────────────────────────────────────────────────
files["src/api/client.ts"] = """import axios from "axios";

// API key read from localStorage (set on first login)
const getKey = () => localStorage.getItem("sentinai_api_key") ?? "";

export const http = axios.create({ baseURL: "/api" });

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
  timestamp: string;   // ISO-8601
  status: "open" | "resolved";
  source?: string;
}

export interface Suggestion {
  patch_id: string;
  rule: string;
  confidence: number;  // 0.0 – 1.0
  explanation: string;
  diff: string;        // unified diff text
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
    live:    () => http.get<{ status: string; service: string }>("/health/live"),
    ready:   () => http.get<ReadinessReport>("/health/ready"),
  },
  stats:          () => http.get<StatsSnapshot>("/stats"),
  incidents:      () => http.get<Incident[]>("/incidents"),
  suggestions:    () => http.get<Suggestion[]>("/suggestions"),
  suggestionLatest: () => http.get<Suggestion>("/suggestions/latest"),
  scanNow:        () => http.post<{ detected_incidents: number }>("/scan-now"),
};
"""

# ── src/App.tsx ───────────────────────────────────────────────────────────
files["src/App.tsx"] = """import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Layout from "@/components/Layout";
import LoginPage from "@/pages/LoginPage";
import IncidentTimeline from "@/pages/IncidentTimeline";
import AuditExplorer from "@/pages/AuditExplorer";
import PolicyEditor from "@/pages/PolicyEditor";
import DiffViewer from "@/pages/DiffViewer";
import { useApiKey } from "@/hooks/useApiKey";

export default function App() {
  const { hasKey } = useApiKey();

  if (!hasKey) return <LoginPage />;

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/incidents" replace />} />
          <Route path="incidents"  element={<IncidentTimeline />} />
          <Route path="audit"      element={<AuditExplorer />} />
          <Route path="policy"     element={<PolicyEditor />} />
          <Route path="diff"       element={<DiffViewer />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
"""

# ── src/hooks/useApiKey.ts ────────────────────────────────────────────────
files["src/hooks/useApiKey.ts"] = """import { useState, useCallback } from "react";

const KEY = "sentinai_api_key";

export function useApiKey() {
  const [hasKey, setHasKey] = useState(() => !!localStorage.getItem(KEY));

  const setKey = useCallback((k: string) => {
    localStorage.setItem(KEY, k.trim());
    setHasKey(true);
  }, []);

  const clearKey = useCallback(() => {
    localStorage.removeItem(KEY);
    setHasKey(false);
  }, []);

  return { hasKey, setKey, clearKey };
}
"""

# ── src/components/Layout.tsx ─────────────────────────────────────────────
files[
    "src/components/Layout.tsx"
] = """import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { useApiKey } from "@/hooks/useApiKey";
import clsx from "clsx";

const NAV = [
  { to: "/incidents", label: "INCIDENTS",  icon: "▲" },
  { to: "/audit",     label: "AUDIT",      icon: "≡" },
  { to: "/policy",    label: "POLICY",     icon: "◈" },
  { to: "/diff",      label: "DIFF",       icon: "±" },
];

export default function Layout() {
  const { clearKey } = useApiKey();
  const navigate = useNavigate();

  const { data: health } = useQuery({
    queryKey: ["health-live"],
    queryFn: () => api.health.live().then((r) => r.data),
    refetchInterval: 15_000,
  });

  const { data: ready } = useQuery({
    queryKey: ["health-ready"],
    queryFn: () => api.health.ready().then((r) => r.data),
    refetchInterval: 30_000,
  });

  const statusColor =
    ready?.status === "ok"       ? "text-ok glow-ok" :
    ready?.status === "degraded" ? "text-warn"        :
    "text-red-500";

  function handleLogout() {
    clearKey();
    navigate("/");
  }

  return (
    <div className="min-h-screen flex flex-col bg-bg">
      {/* ── Top bar ───────────────────────────────────────────────────── */}
      <header className="border-b border-bg-border px-6 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <svg width="24" height="24" viewBox="0 0 32 32" className="shrink-0">
            <polygon points="16,3 29,10 29,22 16,29 3,22 3,10"
              fill="none" stroke="#00d4ff" strokeWidth="2"/>
            <circle cx="16" cy="16" r="4" fill="#00d4ff"/>
          </svg>
          <span className="text-accent font-display font-medium tracking-widest text-sm glow-text">
            SENTINAI
          </span>
          <span className="text-muted text-xs tracking-wider">// SECURITY OPERATIONS</span>
        </div>

        <div className="flex items-center gap-6 text-xs">
          {/* System status */}
          <div className="flex items-center gap-2">
            <span className={clsx("font-medium", statusColor)}>
              ● {ready?.status?.toUpperCase() ?? "—"}
            </span>
            <span className="text-muted">{health?.service ?? "sentinai"}</span>
          </div>

          {/* Readiness checks mini bar */}
          {ready?.checks && (
            <div className="hidden md:flex items-center gap-1">
              {ready.checks.map((c) => (
                <div
                  key={c.name}
                  title={`${c.name}: ${c.status}`}
                  className={clsx(
                    "w-1.5 h-4 rounded-sm",
                    c.status === "ok"       ? "bg-ok" :
                    c.status === "degraded" ? "bg-warn" : "bg-red-500"
                  )}
                />
              ))}
            </div>
          )}

          <button
            onClick={handleLogout}
            className="text-muted hover:text-text transition-colors tracking-wider"
          >
            [LOGOUT]
          </button>
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        {/* ── Sidebar ───────────────────────────────────────────────────── */}
        <nav className="w-44 border-r border-bg-border shrink-0 py-6 flex flex-col gap-1 px-3">
          {NAV.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                clsx(
                  "flex items-center gap-2 px-3 py-2 text-xs tracking-widest transition-all rounded-sm",
                  isActive
                    ? "text-accent bg-accent/5 border-l-2 border-accent glow-text"
                    : "text-muted hover:text-text hover:bg-bg-card border-l-2 border-transparent"
                )
              }
            >
              <span className="w-4 text-center">{icon}</span>
              {label}
            </NavLink>
          ))}

          <div className="mt-auto pt-6 px-3 text-xs text-muted border-t border-bg-border">
            <div className="mb-1 tracking-wider">SYSTEM</div>
            {ready?.checks?.slice(0, 3).map((c) => (
              <div key={c.name} className="flex justify-between py-0.5">
                <span className="truncate">{c.name}</span>
                <span className={
                  c.status === "ok" ? "text-ok" :
                  c.status === "degraded" ? "text-warn" : "text-red-500"
                }>
                  {c.status === "ok" ? "OK" : c.status === "degraded" ? "DEG" : "FAIL"}
                </span>
              </div>
            ))}
          </div>
        </nav>

        {/* ── Main content ──────────────────────────────────────────────── */}
        <main className="flex-1 overflow-auto p-6 animate-fade-in">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
"""

# ── src/pages/LoginPage.tsx ───────────────────────────────────────────────
files["src/pages/LoginPage.tsx"] = """import { useState, FormEvent } from "react";
import { useApiKey } from "@/hooks/useApiKey";

export default function LoginPage() {
  const { setKey } = useApiKey();
  const [value, setValue] = useState("");
  const [error, setError] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!value.trim()) {
      setError("API key required");
      return;
    }
    setKey(value.trim());
  }

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="flex items-center gap-3 mb-12 justify-center">
          <svg width="32" height="32" viewBox="0 0 32 32">
            <polygon points="16,3 29,10 29,22 16,29 3,22 3,10"
              fill="none" stroke="#00d4ff" strokeWidth="2"/>
            <circle cx="16" cy="16" r="4" fill="#00d4ff"/>
          </svg>
          <span className="text-accent text-xl font-display tracking-widest glow-text">
            SENTINAI
          </span>
        </div>

        <div className="border border-bg-border bg-bg-card p-8 rounded-sm">
          <div className="text-xs text-muted tracking-widest mb-6">
            // AUTHENTICATE — SECURITY OPERATIONS CONSOLE
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div>
              <label className="block text-xs text-muted tracking-wider mb-2">
                API KEY
              </label>
              <input
                type="password"
                value={value}
                onChange={(e) => { setValue(e.target.value); setError(""); }}
                placeholder="sk-sentinai-••••••••"
                className="w-full bg-bg border border-bg-border text-text text-sm px-4 py-3
                           font-mono rounded-sm outline-none
                           focus:border-accent focus:shadow-glow-accent transition-all
                           placeholder:text-muted/40"
                autoFocus
              />
              {error && (
                <p className="text-warn text-xs mt-2 tracking-wide">{error}</p>
              )}
            </div>

            <button
              type="submit"
              className="mt-2 w-full bg-accent/10 border border-accent text-accent
                         text-xs tracking-widest py-3 rounded-sm
                         hover:bg-accent hover:text-bg transition-all duration-200
                         hover:shadow-glow-accent"
            >
              AUTHENTICATE →
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-muted mt-6 tracking-wider">
          SET YOUR KEY VIA <span className="text-accent">SENTINAI_API_KEY</span> ENV VAR
        </p>
      </div>
    </div>
  );
}
"""

# ── src/components/SeverityBadge.tsx ─────────────────────────────────────
files["src/components/SeverityBadge.tsx"] = """import clsx from "clsx";

const MAP = {
  critical: "border-red-500   text-red-400   bg-red-500/5",
  high:     "border-warn      text-warn      bg-warn/5",
  medium:   "border-yellow-500 text-yellow-400 bg-yellow-500/5",
  low:      "border-ok        text-ok        bg-ok/5",
} as const;

type Severity = keyof typeof MAP;

export default function SeverityBadge({ level }: { level: Severity }) {
  return (
    <span className={clsx(
      "inline-block border text-[10px] font-display tracking-widest px-2 py-0.5 rounded-sm uppercase",
      MAP[level] ?? MAP.low
    )}>
      {level}
    </span>
  );
}
"""

# ── src/components/StatCard.tsx ───────────────────────────────────────────
files["src/components/StatCard.tsx"] = """interface Props {
  label: string;
  value: string | number;
  sub?: string;
  accent?: boolean;
}

export default function StatCard({ label, value, sub, accent }: Props) {
  return (
    <div className="border border-bg-border bg-bg-card px-5 py-4 rounded-sm">
      <div className="text-xs text-muted tracking-widest mb-2">{label}</div>
      <div className={`text-2xl font-display font-medium ${accent ? "text-accent glow-text" : "text-text"}`}>
        {value}
      </div>
      {sub && <div className="text-xs text-muted mt-1">{sub}</div>}
    </div>
  );
}
"""

# ── src/components/EmptyState.tsx ─────────────────────────────────────────
files[
    "src/components/EmptyState.tsx"
] = """export default function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-muted">
      <div className="text-4xl mb-4 opacity-20">◈</div>
      <p className="text-xs tracking-widest">{message}</p>
    </div>
  );
}
"""

# ── src/components/ErrorBanner.tsx ────────────────────────────────────────
files[
    "src/components/ErrorBanner.tsx"
] = """export default function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="border border-warn/40 bg-warn/5 text-warn text-xs px-4 py-3 rounded-sm tracking-wide">
      ▲ {message}
    </div>
  );
}
"""

# ── src/pages/IncidentTimeline.tsx ────────────────────────────────────────
files["src/pages/IncidentTimeline.tsx"] = """import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type Incident } from "@/api/client";
import { format, parseISO } from "date-fns";
import SeverityBadge from "@/components/SeverityBadge";
import StatCard from "@/components/StatCard";
import EmptyState from "@/components/EmptyState";
import ErrorBanner from "@/components/ErrorBanner";
import clsx from "clsx";

function severityOrder(s: string) {
  return { critical: 0, high: 1, medium: 2, low: 3 }[s] ?? 4;
}

export default function IncidentTimeline() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState<string>("all");

  const { data: incidents = [], isLoading, error } = useQuery({
    queryKey: ["incidents"],
    queryFn: () => api.incidents().then((r) => r.data),
    refetchInterval: 15_000,
  });

  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: () => api.stats().then((r) => r.data),
    refetchInterval: 30_000,
  });

  const scanMut = useMutation({
    mutationFn: () => api.scanNow().then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["incidents"] }),
  });

  const sorted = [...incidents].sort(
    (a, b) => severityOrder(a.severity) - severityOrder(b.severity) ||
              new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  );

  const filtered = filter === "all"
    ? sorted
    : sorted.filter((i) => i.severity === filter || i.status === filter);

  const critCount = incidents.filter((i) => i.severity === "critical").length;
  const openCount = incidents.filter((i) => i.status === "open").length;

  return (
    <div className="space-y-6 animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-sm font-display tracking-widest text-text">
            INCIDENT TIMELINE
          </h1>
          <p className="text-xs text-muted mt-1 tracking-wide">
            Real-time security event feed — auto-refresh every 15s
          </p>
        </div>
        <button
          onClick={() => scanMut.mutate()}
          disabled={scanMut.isPending}
          className={clsx(
            "text-xs tracking-widest px-4 py-2 border rounded-sm transition-all",
            scanMut.isPending
              ? "text-muted border-bg-border cursor-wait"
              : "text-accent border-accent hover:bg-accent hover:text-bg hover:shadow-glow-accent"
          )}
        >
          {scanMut.isPending ? "SCANNING…" : "▷ SCAN NOW"}
        </button>
      </div>

      {/* Scan feedback */}
      {scanMut.isSuccess && (
        <div className="text-xs text-ok tracking-wide border border-ok/30 bg-ok/5 px-4 py-2 rounded-sm">
          ✓ Scan complete — {scanMut.data?.detected_incidents ?? 0} incident(s) detected
        </div>
      )}

      {/* Stat row */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard label="TOTAL SCANS"    value={stats.total_suggestions} />
          <StatCard label="OPEN"           value={openCount}   accent={openCount > 0} />
          <StatCard label="CRITICAL"       value={critCount}   accent={critCount > 0} />
          <StatCard
            label="AVG LATENCY"
            value={stats.avg_latency_ms != null ? `${stats.avg_latency_ms}ms` : "—"}
            sub={stats.p95_latency_ms != null ? `p95: ${stats.p95_latency_ms}ms` : undefined}
          />
        </div>
      )}

      {/* Filter bar */}
      <div className="flex gap-2 flex-wrap">
        {["all", "critical", "high", "medium", "low", "open", "resolved"].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={clsx(
              "text-[10px] tracking-widest px-3 py-1 border rounded-sm uppercase transition-all",
              filter === f
                ? "border-accent text-accent bg-accent/5"
                : "border-bg-border text-muted hover:text-text hover:border-text/30"
            )}
          >
            {f}
          </button>
        ))}
        <span className="ml-auto text-xs text-muted self-center">
          {filtered.length} / {incidents.length}
        </span>
      </div>

      {/* Error */}
      {error && <ErrorBanner message="Failed to load incidents. Check API key and backend." />}

      {/* Timeline */}
      {isLoading ? (
        <div className="text-xs text-muted tracking-widest animate-pulse">LOADING…</div>
      ) : filtered.length === 0 ? (
        <EmptyState message="NO INCIDENTS MATCH FILTER" />
      ) : (
        <div className="relative space-y-0">
          {/* Vertical line */}
          <div className="absolute left-[7px] top-0 bottom-0 w-px bg-bg-border" />

          {filtered.map((incident, i) => (
            <IncidentRow key={incident.id} incident={incident} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}

function IncidentRow({ incident, index }: { incident: Incident; index: number }) {
  const [open, setOpen] = useState(false);

  const dotColor =
    incident.severity === "critical" ? "bg-red-500 shadow-[0_0_8px_#ef4444]" :
    incident.severity === "high"     ? "bg-warn shadow-[0_0_8px_#ff6b35]"    :
    incident.severity === "medium"   ? "bg-yellow-500"                         :
    "bg-ok";

  const ts = (() => {
    try { return format(parseISO(incident.timestamp), "MMM dd HH:mm:ss"); }
    catch { return incident.timestamp; }
  })();

  return (
    <div
      className="relative pl-6 pb-4 cursor-pointer group"
      style={{ animationDelay: `${index * 40}ms` }}
      onClick={() => setOpen((o) => !o)}
    >
      {/* Timeline dot */}
      <div className={clsx("absolute left-0 top-1.5 w-3.5 h-3.5 rounded-full border-2 border-bg", dotColor)} />

      <div className={clsx(
        "border border-bg-border bg-bg-card px-4 py-3 rounded-sm transition-all",
        "group-hover:border-accent/30",
        open && "border-accent/20 bg-bg-card/80"
      )}>
        <div className="flex items-start gap-3 flex-wrap">
          <SeverityBadge level={incident.severity} />
          <span className="text-xs text-muted font-mono">{ts}</span>
          {incident.status === "resolved" && (
            <span className="text-[10px] text-ok tracking-widest border border-ok/30 px-1.5 py-0.5 rounded-sm">
              RESOLVED
            </span>
          )}
          <span className="ml-auto text-muted text-xs">{open ? "▲" : "▼"}</span>
        </div>

        <p className="text-sm text-text mt-2 leading-relaxed">{incident.title}</p>

        {open && (
          <div className="mt-3 pt-3 border-t border-bg-border space-y-2 animate-fade-in">
            <p className="text-xs text-muted leading-relaxed">{incident.description}</p>
            <div className="text-[10px] text-muted/60 tracking-wider font-mono">
              ID: {incident.id}
              {incident.source && ` · SOURCE: ${incident.source}`}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
"""

# ── src/pages/AuditExplorer.tsx ───────────────────────────────────────────
files["src/pages/AuditExplorer.tsx"] = """import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type Suggestion } from "@/api/client";
import { format, parseISO } from "date-fns";
import EmptyState from "@/components/EmptyState";
import ErrorBanner from "@/components/ErrorBanner";

export default function AuditExplorer() {
  const [q, setQ] = useState("");

  const { data: suggestions = [], isLoading, error } = useQuery({
    queryKey: ["suggestions"],
    queryFn: () => api.suggestions().then((r) => r.data),
    refetchInterval: 30_000,
  });

  const filtered = useMemo(() => {
    if (!q.trim()) return suggestions;
    const lower = q.toLowerCase();
    return suggestions.filter(
      (s) =>
        s.rule.toLowerCase().includes(lower) ||
        s.explanation.toLowerCase().includes(lower) ||
        s.patch_id.toLowerCase().includes(lower)
    );
  }, [suggestions, q]);

  return (
    <div className="space-y-6 animate-slide-up">
      {/* Header */}
      <div>
        <h1 className="text-sm font-display tracking-widest text-text">AUDIT EXPLORER</h1>
        <p className="text-xs text-muted mt-1 tracking-wide">
          Searchable record of AI remediation suggestions
        </p>
      </div>

      {/* Search */}
      <div className="relative">
        <span className="absolute left-4 top-1/2 -translate-y-1/2 text-muted text-xs">SEARCH //</span>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="rule, explanation, patch_id…"
          className="w-full bg-bg-card border border-bg-border text-text text-xs
                     pl-[88px] pr-4 py-3 font-mono rounded-sm outline-none
                     focus:border-accent transition-all placeholder:text-muted/40"
        />
        {q && (
          <button
            onClick={() => setQ("")}
            className="absolute right-4 top-1/2 -translate-y-1/2 text-muted hover:text-text text-xs"
          >
            [CLR]
          </button>
        )}
      </div>

      {/* Count */}
      <div className="text-xs text-muted tracking-wider">
        {filtered.length} of {suggestions.length} records
      </div>

      {error && <ErrorBanner message="Failed to load suggestions." />}

      {/* Table */}
      {isLoading ? (
        <div className="text-xs text-muted animate-pulse tracking-widest">LOADING…</div>
      ) : filtered.length === 0 ? (
        <EmptyState message="NO RECORDS FOUND" />
      ) : (
        <div className="border border-bg-border rounded-sm overflow-hidden">
          {/* Header row */}
          <div className="grid grid-cols-[1fr_2fr_auto_auto] gap-4 px-4 py-2
                          bg-bg-card border-b border-bg-border
                          text-[10px] text-muted tracking-widest uppercase">
            <span>PATCH ID</span>
            <span>RULE / EXPLANATION</span>
            <span>CONFIDENCE</span>
            <span>TIME</span>
          </div>

          {filtered.map((s, i) => (
            <AuditRow key={s.patch_id} suggestion={s} index={i} total={filtered.length} />
          ))}
        </div>
      )}
    </div>
  );
}

function AuditRow({
  suggestion: s,
  index,
  total,
}: {
  suggestion: Suggestion;
  index: number;
  total: number;
}) {
  const [open, setOpen] = useState(false);
  const pct = Math.round(s.confidence * 100);

  const ts = (() => {
    try { return s.created_at ? format(parseISO(s.created_at), "MMM dd HH:mm") : "—"; }
    catch { return "—"; }
  })();

  const barColor =
    pct >= 80 ? "bg-ok"   :
    pct >= 50 ? "bg-warn" : "bg-red-500";

  return (
    <>
      <div
        onClick={() => setOpen((o) => !o)}
        className={`grid grid-cols-[1fr_2fr_auto_auto] gap-4 px-4 py-3 cursor-pointer
                    text-xs border-b transition-all hover:bg-bg-card/60
                    ${index === total - 1 ? "border-transparent" : "border-bg-border"}`}
      >
        <span className="text-accent font-mono text-[11px] truncate" title={s.patch_id}>
          {s.patch_id.slice(0, 12)}…
        </span>
        <span className="text-text truncate" title={s.explanation}>
          <span className="text-muted">{s.rule}</span>
          {" · "}
          {s.explanation.slice(0, 60)}{s.explanation.length > 60 ? "…" : ""}
        </span>
        <div className="flex items-center gap-2 w-20">
          <div className="flex-1 h-1 bg-bg-border rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${barColor}`}
              style={{ width: `${pct}%` }}
            />
          </div>
          <span className={`text-[10px] w-7 text-right ${barColor.replace("bg-", "text-")}`}>
            {pct}%
          </span>
        </div>
        <span className="text-muted w-20 text-right">{ts}</span>
      </div>

      {open && (
        <div className="px-4 py-3 bg-bg border-b border-bg-border animate-fade-in">
          <div className="text-[10px] text-muted tracking-wider mb-2">FULL EXPLANATION</div>
          <p className="text-xs text-text leading-relaxed">{s.explanation}</p>
          <div className="mt-2 text-[10px] text-muted/60">
            PATCH_ID: {s.patch_id}
          </div>
        </div>
      )}
    </>
  );
}
"""

# ── src/pages/PolicyEditor.tsx ────────────────────────────────────────────
files["src/pages/PolicyEditor.tsx"] = """import { useState } from "react";

const EXAMPLE_POLICY = `# SentinAI Policy Configuration
# Edit and validate your security rules here.

version: "1.0"

rules:
  - id: AUTH001
    description: "Require authentication on all admin routes"
    severity: critical
    enabled: true

  - id: PRIV001
    description: "Prevent privilege escalation via sudo"
    severity: high
    enabled: true

  - id: SEC001
    description: "Block hardcoded secrets in source"
    severity: critical
    enabled: true

  - id: TAINT001
    description: "Flag unsanitized user input in SQL"
    severity: high
    enabled: true

thresholds:
  min_confidence: 0.7
  auto_apply: false
  notify_on: [critical, high]
`.trim();

export default function PolicyEditor() {
  const [content, setContent] = useState(EXAMPLE_POLICY);
  const [status, setStatus] = useState<"idle" | "ok" | "error">("idle");
  const [message, setMessage] = useState("");

  function validate() {
    // Client-side YAML structure validation
    try {
      const lines = content.split("\\n");
      const hasVersion = lines.some((l) => l.trim().startsWith("version:"));
      const hasRules   = lines.some((l) => l.trim().startsWith("rules:"));
      if (!hasVersion || !hasRules) throw new Error("Missing required fields: version, rules");
      setStatus("ok");
      setMessage("Policy structure valid — ready to apply");
    } catch (e) {
      setStatus("error");
      setMessage(e instanceof Error ? e.message : "Validation failed");
    }
  }

  const lineCount = content.split("\\n").length;

  return (
    <div className="space-y-6 animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-sm font-display tracking-widest text-text">POLICY EDITOR</h1>
          <p className="text-xs text-muted mt-1 tracking-wide">
            Edit sentinai-policy.yml — validate before applying
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={validate}
            className="text-xs tracking-widest px-4 py-2 border border-accent text-accent
                       hover:bg-accent hover:text-bg rounded-sm transition-all hover:shadow-glow-accent"
          >
            ◈ VALIDATE
          </button>
        </div>
      </div>

      {/* Status bar */}
      {status !== "idle" && (
        <div className={`text-xs px-4 py-2 border rounded-sm tracking-wide
          ${status === "ok"
            ? "border-ok/30 bg-ok/5 text-ok"
            : "border-warn/40 bg-warn/5 text-warn"}`}>
          {status === "ok" ? "✓" : "▲"} {message}
        </div>
      )}

      {/* Editor area */}
      <div className="border border-bg-border rounded-sm overflow-hidden">
        {/* Editor toolbar */}
        <div className="flex items-center justify-between px-4 py-2
                        bg-bg-card border-b border-bg-border">
          <span className="text-[10px] text-muted tracking-widest">
            YAML · sentinai-policy.yml
          </span>
          <div className="flex gap-4 text-[10px] text-muted">
            <span>{lineCount} lines</span>
            <span>{content.length} chars</span>
          </div>
        </div>

        {/* Line numbers + textarea */}
        <div className="flex font-mono text-xs">
          {/* Line numbers */}
          <div className="select-none bg-bg px-3 py-4 text-right text-muted/40
                          border-r border-bg-border min-w-[3rem] leading-6">
            {Array.from({ length: lineCount }, (_, i) => (
              <div key={i}>{i + 1}</div>
            ))}
          </div>

          {/* Textarea */}
          <textarea
            value={content}
            onChange={(e) => { setContent(e.target.value); setStatus("idle"); }}
            spellCheck={false}
            className="flex-1 bg-bg text-text px-4 py-4 outline-none resize-none
                       leading-6 min-h-[420px] font-mono text-xs"
          />
        </div>
      </div>

      <p className="text-[10px] text-muted/50 tracking-wider">
        // Changes are local only — apply via CLI: <span className="text-accent">sentinai apply-policy</span>
      </p>
    </div>
  );
}
"""

# ── src/pages/DiffViewer.tsx ──────────────────────────────────────────────
files["src/pages/DiffViewer.tsx"] = """import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type Suggestion } from "@/api/client";
import EmptyState from "@/components/EmptyState";
import ErrorBanner from "@/components/ErrorBanner";
import clsx from "clsx";

function renderDiff(raw: string) {
  return raw.split("\\n").map((line, i) => {
    const isAdd    = line.startsWith("+") && !line.startsWith("+++");
    const isRemove = line.startsWith("-") && !line.startsWith("---");
    const isHunk   = line.startsWith("@@");
    const isMeta   = line.startsWith("---") || line.startsWith("+++");

    return (
      <div
        key={i}
        className={clsx(
          "flex gap-2 px-4 leading-6 text-[11px] font-mono",
          isAdd    && "bg-ok/5 text-ok",
          isRemove && "bg-red-500/5 text-red-400",
          isHunk   && "bg-accent/5 text-accent",
          isMeta   && "text-muted",
          !isAdd && !isRemove && !isHunk && !isMeta && "text-text/80"
        )}
      >
        <span className="select-none w-4 shrink-0 text-muted/40">
          {isAdd ? "+" : isRemove ? "−" : " "}
        </span>
        <span className="whitespace-pre">{line.slice(isAdd || isRemove ? 1 : 0)}</span>
      </div>
    );
  });
}

export default function DiffViewer() {
  const [selected, setSelected] = useState<string | null>(null);

  const { data: suggestions = [], isLoading, error } = useQuery({
    queryKey: ["suggestions"],
    queryFn: () => api.suggestions().then((r) => r.data),
    refetchInterval: 30_000,
  });

  const active = suggestions.find((s) => s.patch_id === selected) ?? suggestions[0];

  return (
    <div className="space-y-6 animate-slide-up">
      <div>
        <h1 className="text-sm font-display tracking-widest text-text">DIFF VIEWER</h1>
        <p className="text-xs text-muted mt-1 tracking-wide">
          Syntax-highlighted patch diffs from remediation suggestions
        </p>
      </div>

      {error && <ErrorBanner message="Failed to load suggestions." />}

      {isLoading ? (
        <div className="text-xs text-muted animate-pulse tracking-widest">LOADING…</div>
      ) : suggestions.length === 0 ? (
        <EmptyState message="NO PATCHES AVAILABLE — RUN A SCAN FIRST" />
      ) : (
        <div className="flex gap-4 min-h-[500px]">
          {/* Patch list */}
          <div className="w-64 shrink-0 border border-bg-border rounded-sm overflow-hidden">
            <div className="px-3 py-2 bg-bg-card border-b border-bg-border
                            text-[10px] text-muted tracking-widest">
              PATCHES · {suggestions.length}
            </div>
            <div className="overflow-y-auto">
              {suggestions.map((s) => {
                const pct = Math.round(s.confidence * 100);
                const isActive = active?.patch_id === s.patch_id;
                return (
                  <button
                    key={s.patch_id}
                    onClick={() => setSelected(s.patch_id)}
                    className={clsx(
                      "w-full text-left px-3 py-3 border-b border-bg-border transition-all",
                      isActive
                        ? "bg-accent/5 border-l-2 border-l-accent"
                        : "hover:bg-bg-card border-l-2 border-l-transparent"
                    )}
                  >
                    <div className="text-[10px] text-accent font-mono truncate">
                      {s.patch_id.slice(0, 14)}
                    </div>
                    <div className="text-[10px] text-muted mt-0.5 truncate">{s.rule}</div>
                    <div className="mt-1.5 flex items-center gap-1.5">
                      <div className="flex-1 h-0.5 bg-bg-border rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${
                            pct >= 80 ? "bg-ok" : pct >= 50 ? "bg-warn" : "bg-red-500"
                          }`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="text-[9px] text-muted">{pct}%</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Diff panel */}
          <div className="flex-1 border border-bg-border rounded-sm overflow-hidden flex flex-col">
            {active ? (
              <>
                {/* Patch meta */}
                <div className="px-4 py-3 bg-bg-card border-b border-bg-border flex items-start justify-between gap-4">
                  <div>
                    <div className="text-xs text-text font-mono">{active.rule}</div>
                    <div className="text-[10px] text-muted mt-1 leading-relaxed max-w-xl">
                      {active.explanation}
                    </div>
                  </div>
                  <div className="text-[10px] text-muted shrink-0 text-right">
                    <div>CONFIDENCE</div>
                    <div className={`text-base font-display ${
                      active.confidence >= 0.8 ? "text-ok" :
                      active.confidence >= 0.5 ? "text-warn" : "text-red-400"
                    }`}>
                      {Math.round(active.confidence * 100)}%
                    </div>
                  </div>
                </div>

                {/* Diff body */}
                <div className="flex-1 overflow-auto py-2 bg-bg">
                  {active.diff
                    ? renderDiff(active.diff)
                    : <div className="px-4 py-4 text-xs text-muted">No diff available for this patch.</div>
                  }
                </div>
              </>
            ) : (
              <EmptyState message="SELECT A PATCH" />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
"""

# ── Write all files ───────────────────────────────────────────────────────
for rel_path, content in files.items():
    dest = BASE / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    print(f"  WROTE  {dest}")

print()
print("Done. Now run:")
print("  cd frontend")
print("  npm install")
print("  npm run dev")
