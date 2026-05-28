import { create } from "zustand";
import { subscribeWithSelector } from "zustand/middleware";
import { api, type Incident, type Suggestion, type StatsSnapshot } from "@/api/client";

/* ── types ────────────────────────────────────────────────────────────── */

interface SentinaiState {
  /* data */
  incidents:   Incident[];
  suggestions: Suggestion[];
  stats:       StatsSnapshot | null;

  /* status */
  incidentsLoading:   boolean;
  suggestionsLoading: boolean;
  statsLoading:       boolean;
  incidentsError:     string | null;

  /* scan */
  scanning:    boolean;
  lastScanAt:  string | null;

  /* actions */
  fetchIncidents:   () => Promise<void>;
  fetchSuggestions: () => Promise<void>;
  fetchStats:       () => Promise<void>;
  fetchAll:         () => Promise<void>;
  triggerScan:      () => Promise<{ detected_incidents: number }>;
}

/* ── derived selectors (use outside component for perf) ──────────────── */

export const selectCriticalCount  = (s: SentinaiState) =>
  s.incidents.filter((i) => i.severity === "critical").length;

export const selectOpenCount      = (s: SentinaiState) =>
  s.incidents.filter((i) => i.status === "open").length;

export const selectResolvedCount  = (s: SentinaiState) =>
  s.incidents.filter((i) => i.status === "resolved").length;

export const selectSortedIncidents = (s: SentinaiState) =>
  [...s.incidents].sort((a, b) => {
    const order: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };
    return (
      (order[a.severity] ?? 4) - (order[b.severity] ?? 4) ||
      new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );
  });

/* ── store ────────────────────────────────────────────────────────────── */

export const useSentinaiStore = create<SentinaiState>()(
  subscribeWithSelector((set, get) => ({
    incidents:   [],
    suggestions: [],
    stats:       null,

    incidentsLoading:   false,
    suggestionsLoading: false,
    statsLoading:       false,
    incidentsError:     null,

    scanning:   false,
    lastScanAt: null,

    fetchIncidents: async () => {
      set({ incidentsLoading: true, incidentsError: null });
      try {
        const { data } = await api.incidents();
        set({ incidents: data, incidentsLoading: false });
      } catch (e) {
        set({ incidentsLoading: false, incidentsError: "Failed to load incidents" });
      }
    },

    fetchSuggestions: async () => {
      set({ suggestionsLoading: true });
      try {
        const { data } = await api.suggestions();
        set({ suggestions: data, suggestionsLoading: false });
      } catch {
        set({ suggestionsLoading: false });
      }
    },

    fetchStats: async () => {
      set({ statsLoading: true });
      try {
        const { data } = await api.stats();
        set({ stats: data, statsLoading: false });
      } catch {
        set({ statsLoading: false });
      }
    },

    fetchAll: async () => {
      const { fetchIncidents, fetchSuggestions, fetchStats } = get();
      await Promise.all([fetchIncidents(), fetchSuggestions(), fetchStats()]);
    },

    triggerScan: async () => {
      set({ scanning: true });
      try {
        const { data } = await api.scanNow();
        set({ scanning: false, lastScanAt: new Date().toISOString() });
        await get().fetchIncidents();
        return data;
      } catch (e) {
        set({ scanning: false });
        throw e;
      }
    },
  }))
);

/* ── auto-polling (call once at app root) ────────────────────────────── */

let _pollTimer: ReturnType<typeof setInterval> | null = null;

export function startPolling(intervalMs = 15_000) {
  if (_pollTimer) return;
  const store = useSentinaiStore.getState();
  store.fetchAll();
  _pollTimer = setInterval(() => {
    useSentinaiStore.getState().fetchAll();
  }, intervalMs);
}

export function stopPolling() {
  if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null; }
}
