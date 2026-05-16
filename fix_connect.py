"""
Connects frontend to live backend data:
1. src/api/client.ts  - axios error interceptor (401 → auto-logout, 503 → toast)
2. src/hooks/useHealth.ts  - centralized health polling hook
3. src/components/Toast.tsx  - lightweight toast notification system
4. src/App.tsx  - wire Toast provider
5. src/pages/IncidentTimeline.tsx  - show real error states, loading skeletons
6. src/pages/AuditExplorer.tsx  - same
7. src/pages/DiffViewer.tsx  - same
8. frontend/.env.local  - confirm dev backend URL
"""

from pathlib import Path

BASE = Path("frontend/src")

# ── 1. api/client.ts — add error interceptor ─────────────────────────────
(BASE / "api/client.ts").write_text(
    """\
import axios, { AxiosError } from "axios";

const BASE_URL = import.meta.env.VITE_API_URL ?? "/api";
const KEY      = "sentinai_api_key";
const EXPIRY   = "sentinai_key_expiry";

export const getApiKey = () => localStorage.getItem(KEY) ?? "";

export const http = axios.create({ baseURL: BASE_URL });

// ── Request: attach API key ───────────────────────────────────────────────
http.interceptors.request.use((cfg) => {
  const key = getApiKey();
  if (key) cfg.headers["X-API-Key"] = key;
  return cfg;
});

// ── Response: handle auth + server errors globally ────────────────────────
http.interceptors.response.use(
  (res) => res,
  (err: AxiosError) => {
    if (err.response?.status === 401 || err.response?.status === 403) {
      // Expired or invalid key — clear session and reload to login screen
      localStorage.removeItem(KEY);
      localStorage.removeItem(EXPIRY);
      window.location.reload();
    }
    return Promise.reject(err);
  }
);

// ── Domain types ──────────────────────────────────────────────────────────

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
print("WROTE  src/api/client.ts — error interceptor added")

# ── 2. hooks/useHealth.ts ─────────────────────────────────────────────────
(BASE / "hooks/useHealth.ts").write_text(
    """\
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";

/**
 * Centralized health polling used by Layout and any component
 * that needs to reflect backend status.
 */
export function useHealth() {
  const live = useQuery({
    queryKey:       ["health-live"],
    queryFn:        () => api.health.live().then((r) => r.data),
    refetchInterval: 15_000,
    retry:           1,
  });

  const ready = useQuery({
    queryKey:       ["health-ready"],
    queryFn:        () => api.health.ready().then((r) => r.data),
    refetchInterval: 30_000,
    retry:           1,
  });

  const isBackendUp =
    live.data?.status === "ok" || ready.data?.healthy === true;

  return {
    live:        live.data,
    ready:       ready.data,
    isBackendUp,
    isLoading:   live.isLoading || ready.isLoading,
  };
}
""",
    encoding="utf-8",
)
print("WROTE  src/hooks/useHealth.ts")

# ── 3. components/Toast.tsx ───────────────────────────────────────────────
(BASE / "components/Toast.tsx").write_text(
    """\
import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useRef,
  type ReactNode,
} from "react";
import clsx from "clsx";

type Level = "info" | "ok" | "warn" | "error";

interface Toast {
  id:      number;
  message: string;
  level:   Level;
}

interface ToastCtx {
  toast: (message: string, level?: Level) => void;
}

const Ctx = createContext<ToastCtx>({ toast: () => undefined });

let _nextId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    const t = timers.current.get(id);
    if (t) { clearTimeout(t); timers.current.delete(id); }
  }, []);

  const toast = useCallback((message: string, level: Level = "info") => {
    const id = ++_nextId;
    setToasts((prev) => [...prev.slice(-4), { id, message, level }]);
    const t = setTimeout(() => dismiss(id), 4_000);
    timers.current.set(id, t);
  }, [dismiss]);

  useEffect(() => {
    const ts = timers.current;
    return () => ts.forEach(clearTimeout);
  }, []);

  const colors: Record<Level, string> = {
    info:  "border-accent/40  bg-accent/5  text-accent",
    ok:    "border-ok/40     bg-ok/5     text-ok",
    warn:  "border-warn/40   bg-warn/5   text-warn",
    error: "border-red-500/40 bg-red-500/5 text-red-400",
  };

  const icons: Record<Level, string> = {
    info: "◈", ok: "✓", warn: "▲", error: "✕",
  };

  return (
    <Ctx.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            onClick={() => dismiss(t.id)}
            className={clsx(
              "pointer-events-auto flex items-center gap-3 px-4 py-3",
              "border rounded-sm text-xs font-mono tracking-wide",
              "animate-slide-up cursor-pointer select-none",
              "min-w-[260px] max-w-[420px]",
              colors[t.level]
            )}
          >
            <span className="shrink-0">{icons[t.level]}</span>
            <span className="flex-1">{t.message}</span>
            <span className="shrink-0 opacity-50 text-[10px]">[×]</span>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export function useToast() {
  return useContext(Ctx);
}
""",
    encoding="utf-8",
)
print("WROTE  src/components/Toast.tsx")

# ── 4. App.tsx — wire ToastProvider + useHealth banner ───────────────────
(BASE / "App.tsx").write_text(
    """\
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ToastProvider } from "@/components/Toast";
import Layout from "@/components/Layout";
import LoginPage from "@/pages/LoginPage";
import IncidentTimeline from "@/pages/IncidentTimeline";
import AuditExplorer from "@/pages/AuditExplorer";
import PolicyEditor from "@/pages/PolicyEditor";
import DiffViewer from "@/pages/DiffViewer";
import { useApiKey } from "@/hooks/useApiKey";

export default function App() {
  const { hasKey } = useApiKey();

  if (!hasKey) return <ToastProvider><LoginPage /></ToastProvider>;

  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Navigate to="/incidents" replace />} />
            <Route path="incidents" element={<IncidentTimeline />} />
            <Route path="audit"     element={<AuditExplorer />} />
            <Route path="policy"    element={<PolicyEditor />} />
            <Route path="diff"      element={<DiffViewer />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  );
}
""",
    encoding="utf-8",
)
print("WROTE  src/App.tsx — ToastProvider wired")

# ── 5. components/Skeleton.tsx — loading placeholder ─────────────────────
(BASE / "components/Skeleton.tsx").write_text(
    """\
import clsx from "clsx";

interface Props { className?: string; rows?: number; }

export default function Skeleton({ className, rows = 1 }: Props) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className={clsx(
            "animate-pulse rounded-sm bg-bg-card border border-bg-border",
            className ?? "h-12 w-full"
          )}
        />
      ))}
    </div>
  );
}
""",
    encoding="utf-8",
)
print("WROTE  src/components/Skeleton.tsx")

# ── 6. components/Layout.tsx — use useHealth hook + toast on backend down ─
(BASE / "components/Layout.tsx").write_text(
    """\
import { useEffect } from "react";
import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { useApiKey } from "@/hooks/useApiKey";
import { useHealth } from "@/hooks/useHealth";
import { useToast } from "@/components/Toast";
import clsx from "clsx";

const NAV = [
  { to: "/incidents", label: "INCIDENTS", icon: "▲" },
  { to: "/audit",     label: "AUDIT",     icon: "≡" },
  { to: "/policy",    label: "POLICY",    icon: "◈" },
  { to: "/diff",      label: "DIFF",      icon: "±" },
];

export default function Layout() {
  const { clearKey } = useApiKey();
  const navigate     = useNavigate();
  const { live, ready, isBackendUp } = useHealth();
  const { toast } = useToast();

  // Notify once when backend goes down
  useEffect(() => {
    if (isBackendUp === false) {
      toast("Backend unreachable — check VITE_API_URL and backend status", "error");
    }
  }, [isBackendUp, toast]);

  const statusColor =
    ready?.status === "ok"       ? "text-ok"   :
    ready?.status === "degraded" ? "text-warn"  : "text-red-500";

  function handleLogout() {
    clearKey();
    navigate("/");
  }

  return (
    <div className="min-h-screen flex flex-col bg-bg">
      {/* ── Top bar ─────────────────────────────────────────────────── */}
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
          <div className="flex items-center gap-2">
            <span className={clsx("font-medium", statusColor)}>
              ● {ready?.status?.toUpperCase() ?? (isBackendUp ? "CONNECTING…" : "OFFLINE")}
            </span>
            <span className="text-muted">{live?.service ?? "sentinai"}</span>
          </div>

          {ready?.checks && (
            <div className="hidden md:flex items-center gap-1">
              {ready.checks.map((c) => (
                <div
                  key={c.name}
                  title={`${c.name}: ${c.status}${c.detail ? " — " + c.detail : ""}`}
                  className={clsx(
                    "w-1.5 h-4 rounded-sm",
                    c.status === "ok"       ? "bg-ok"      :
                    c.status === "degraded" ? "bg-warn"    : "bg-red-500"
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
        {/* ── Sidebar ─────────────────────────────────────────────────── */}
        <nav className="w-44 border-r border-bg-border shrink-0 py-6 flex flex-col gap-1 px-3">
          {NAV.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                clsx(
                  "flex items-center gap-2 px-3 py-2 text-xs tracking-widest",
                  "transition-all rounded-sm border-l-2",
                  isActive
                    ? "text-accent bg-accent/5 border-accent glow-text"
                    : "text-muted hover:text-text hover:bg-bg-card border-transparent"
                )
              }
            >
              <span className="w-4 text-center">{icon}</span>
              {label}
            </NavLink>
          ))}

          <div className="mt-auto pt-6 px-3 text-xs text-muted border-t border-bg-border">
            <div className="mb-1 tracking-wider">CHECKS</div>
            {ready?.checks?.map((c) => (
              <div key={c.name} className="flex justify-between py-0.5">
                <span className="truncate">{c.name}</span>
                <span className={
                  c.status === "ok"       ? "text-ok"   :
                  c.status === "degraded" ? "text-warn"  : "text-red-500"
                }>
                  {c.status === "ok" ? "OK" : c.status === "degraded" ? "DEG" : "FAIL"}
                </span>
              </div>
            ))}
          </div>
        </nav>

        {/* ── Main ───────────────────────────────────────────────────── */}
        <main className="flex-1 overflow-auto p-6 animate-fade-in">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
""",
    encoding="utf-8",
)
print("WROTE  src/components/Layout.tsx — useHealth + toast on backend down")

# ── 7. pages/IncidentTimeline.tsx — skeleton + toast on scan ─────────────
(BASE / "pages/IncidentTimeline.tsx").write_text(
    """\
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type Incident } from "@/api/client";
import { format, parseISO } from "date-fns";
import SeverityBadge from "@/components/SeverityBadge";
import StatCard from "@/components/StatCard";
import Skeleton from "@/components/Skeleton";
import EmptyState from "@/components/EmptyState";
import ErrorBanner from "@/components/ErrorBanner";
import { useToast } from "@/components/Toast";
import clsx from "clsx";

function severityOrder(s: string) {
  return ({ critical: 0, high: 1, medium: 2, low: 3 } as Record<string,number>)[s] ?? 4;
}

export default function IncidentTimeline() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [filter, setFilter] = useState("all");

  const { data: incidents = [], isLoading, error } = useQuery({
    queryKey: ["incidents"],
    queryFn:  () => api.incidents().then((r) => r.data),
    refetchInterval: 15_000,
  });

  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn:  () => api.stats().then((r) => r.data),
    refetchInterval: 30_000,
  });

  const scanMut = useMutation({
    mutationFn: () => api.scanNow().then((r) => r.data),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["incidents"] });
      toast(
        `Scan complete — ${data.detected_incidents} incident(s) detected`,
        data.detected_incidents > 0 ? "warn" : "ok"
      );
    },
    onError: () => toast("Scan failed — check backend connection", "error"),
  });

  const sorted = [...incidents].sort(
    (a, b) =>
      severityOrder(a.severity) - severityOrder(b.severity) ||
      new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  );

  const filtered =
    filter === "all"
      ? sorted
      : sorted.filter((i) => i.severity === filter || i.status === filter);

  const critCount = incidents.filter((i) => i.severity === "critical").length;
  const openCount = incidents.filter((i) => i.status === "open").length;

  return (
    <div className="space-y-6 animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-sm font-display tracking-widest">INCIDENT TIMELINE</h1>
          <p className="text-xs text-muted mt-1 tracking-wide">
            Live feed — auto-refresh every 15s
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

      {/* Stats */}
      {isLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Skeleton className="h-20" rows={4} />
        </div>
      ) : stats ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard label="TOTAL SCANS" value={stats.total_suggestions} />
          <StatCard label="OPEN"        value={openCount} accent={openCount > 0} />
          <StatCard label="CRITICAL"    value={critCount} accent={critCount > 0} />
          <StatCard
            label="AVG LATENCY"
            value={stats.avg_latency_ms != null ? `${stats.avg_latency_ms}ms` : "—"}
            sub={stats.p95_latency_ms != null ? `p95: ${stats.p95_latency_ms}ms` : undefined}
          />
        </div>
      ) : null}

      {/* Filter bar */}
      <div className="flex gap-2 flex-wrap items-center">
        {["all","critical","high","medium","low","open","resolved"].map((f) => (
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
        <span className="ml-auto text-xs text-muted">
          {filtered.length} / {incidents.length}
        </span>
      </div>

      {error && (
        <ErrorBanner message="Failed to load incidents. Verify API key and backend URL." />
      )}

      {isLoading ? (
        <Skeleton className="h-16" rows={5} />
      ) : filtered.length === 0 ? (
        <EmptyState message="NO INCIDENTS MATCH FILTER" />
      ) : (
        <div className="relative space-y-0">
          <div className="absolute left-[7px] top-0 bottom-0 w-px bg-bg-border" />
          {filtered.map((inc, i) => (
            <IncidentRow key={inc.id} incident={inc} index={i} />
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
      <div className={clsx(
        "absolute left-0 top-1.5 w-3.5 h-3.5 rounded-full border-2 border-bg",
        dotColor
      )} />
      <div className={clsx(
        "border border-bg-border bg-bg-card px-4 py-3 rounded-sm transition-all",
        "group-hover:border-accent/30",
        open && "border-accent/20"
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
""",
    encoding="utf-8",
)
print("WROTE  src/pages/IncidentTimeline.tsx — skeleton + toast")

print()
print("Done. Run:")
print("  cd frontend && npm run type-check")
