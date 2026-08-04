import axios, { AxiosError } from "axios";

const BASE_URL = import.meta.env.VITE_API_URL ?? "";
export const KEY = "sentinai_api_key";
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
    if ((err.response?.status === 401 || err.response?.status === 403) && !(err.config as any)?.skipAuthRedirect) {
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
  service?: string;
  log_file_path?: string;
  llm_provider?: string;
  buffer_incident_count?: number;
  buffer_suggestion_count?: number;
  dedupe_fingerprints_tracked?: number;
  total_scan_runs?: number;
  last_scan_at_utc?: string | null;
  last_scan_new_incidents?: number;
  dedupe_window_max?: number;
  recent_suggestions_by_source?: {
    stub: number;
    provider: number;
    fallback: number;
  };
  llm_metrics?: {
    total_suggestions: number;
    total_fallbacks: number;
    fallback_rate: number;
    avg_latency_ms: number | null;
    p95_latency_ms: number | null;
    p99_latency_ms: number | null;
    latency_sample_count: number;
  };
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

export interface AutonomySettings {
  mode: "propose_only" | "auto_pr";
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
  validateKey:      () => http.get<StatsSnapshot>("/stats", { skipAuthRedirect: true } as any),
  settings: {
    getAutonomy: () => http.get<AutonomySettings>("/settings/autonomy"),
    setAutonomy: (mode: AutonomySettings["mode"]) =>
      http.patch<AutonomySettings>("/settings/autonomy", { mode }),
  },
};
