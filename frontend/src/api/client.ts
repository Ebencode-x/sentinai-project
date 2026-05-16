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
