import axios, { AxiosError } from "axios";
import { getStoredToken } from "@/hooks/useAuth";

const BASE_URL = import.meta.env.VITE_API_URL ?? "";

export const http = axios.create({ baseURL: BASE_URL });

// ── Request: attach session token ──────────────────────────────────────────
http.interceptors.request.use((cfg) => {
  const token = getStoredToken();
  if (token) cfg.headers["X-Session-Token"] = token;
  return cfg;
});

// ── Response: handle auth + server errors globally ────────────────────────
http.interceptors.response.use(
  (res) => res,
  (err: AxiosError) => {
    if ((err.response?.status === 401 || err.response?.status === 403) && !(err.config as any)?.skipAuthRedirect) {
      // Expired or invalid session — clear it and reload to login screen
      localStorage.removeItem("sentinai_session_token");
      localStorage.removeItem("sentinai_session_user");
      localStorage.removeItem("sentinai_session_expiry");
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
  id: string;
  created_at_utc: string;
  summary: string;
  proposed_code_fix: string;
  proposed_config_change: string;
  confidence: number;
  risks: string;
  source: "stub" | "provider" | "fallback";
  provider_error?: string | null;
  proposed_patch?: string | null;
  test_guidance?: string | null;
  pr_url?: string | null;
  patch_file?: string | null;
  autonomy_mode?: string | null;
  awaiting_approval?: boolean;
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

export interface NotificationChannel {
  id: string;
  name: string;
  type: "slack" | "webhook";
  url: string;
  severities: Array<"warning" | "critical">;
  enabled: boolean;
}

export interface ChannelCreatePayload {
  name: string;
  type: "slack" | "webhook";
  url: string;
  severities: Array<"warning" | "critical">;
  enabled?: boolean;
}

export interface ChannelUpdatePayload {
  name?: string;
  url?: string;
  severities?: Array<"warning" | "critical">;
  enabled?: boolean;
}

// ── API surface ────────────────────────────────────────────────────────────

export const api = {
  health: {
    live: () => http.get<{ status: string; service: string }>("/health/live"),
    ready: () => http.get<ReadinessReport>("/health/ready"),
  },
  stats: () => http.get<StatsSnapshot>("/stats"),
  incidents: () => http.get<Incident[]>("/incidents"),
  suggestions: () => http.get<Suggestion[]>("/suggestions"),
  suggestionLatest: () => http.get<Suggestion>("/suggestions/latest"),
  scanNow: () => http.post<{ detected_incidents: number }>("/scan-now"),
  settings: {
    getAutonomy: () => http.get<AutonomySettings>("/settings/autonomy"),
    setAutonomy: (mode: AutonomySettings["mode"]) =>
      http.patch<AutonomySettings>("/settings/autonomy", { mode }),
    listChannels: () => http.get<NotificationChannel[]>("/settings/channels"),
    createChannel: (payload: ChannelCreatePayload) =>
      http.post<NotificationChannel>("/settings/channels", payload),
    updateChannel: (id: string, payload: ChannelUpdatePayload) =>
      http.patch<NotificationChannel>(`/settings/channels/${id}`, payload),
    deleteChannel: (id: string) =>
      http.delete<{ deleted: boolean; id: string }>(`/settings/channels/${id}`),
  },
};
