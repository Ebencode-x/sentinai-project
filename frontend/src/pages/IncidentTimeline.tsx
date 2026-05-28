import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type Incident } from "@/api/client";
import { format, parseISO } from "date-fns";
import SeverityBadge from "@/components/SeverityBadge";
import Skeleton from "@/components/Skeleton";
import EmptyState from "@/components/EmptyState";
import ErrorBanner from "@/components/ErrorBanner";
import { useToast } from "@/components/Toast";
import { RefreshCw, Radio, Clock, Hash } from "lucide-react";

const SEV_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };

const SEV_GLOW: Record<string, string> = {
  critical: "var(--red)",
  high:     "var(--amber)",
  medium:   "var(--amber)",
  low:      "var(--green)",
};

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
      toast(`scan complete — ${data.detected_incidents} new`, data.detected_incidents > 0 ? "warn" : "ok");
    },
    onError: () => toast("scan failed", "error"),
  });

  const sorted = [...incidents].sort(
    (a, b) =>
      (SEV_ORDER[a.severity] ?? 4) - (SEV_ORDER[b.severity] ?? 4) ||
      new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  );

  const filtered = filter === "all"
    ? sorted
    : sorted.filter((i) => i.severity === filter || i.status === filter);

  const critCount = incidents.filter((i) => i.severity === "critical").length;
  const openCount = incidents.filter((i) => i.status  === "open").length;

  const FILTERS = ["all","critical","high","medium","low","open","resolved"];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px",
      animation: "slideUp 0.3s ease-out both" }}>

      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
        <div>
          <h1 style={{ fontFamily: "'Syne', sans-serif", fontSize: "13px", fontWeight: 700,
            letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--text-primary)" }}>
            Incident Timeline
          </h1>
          <p style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
            color: "var(--text-muted)", marginTop: "4px", letterSpacing: "0.04em" }}>
            live · auto-refresh 15s
          </p>
        </div>
        <button
          onClick={() => scanMut.mutate()}
          disabled={scanMut.isPending}
          style={{
            display: "flex", alignItems: "center", gap: "6px",
            fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
            letterSpacing: "0.1em", padding: "8px 16px",
            border: scanMut.isPending ? "0.5px solid var(--border)" : "0.5px solid var(--cyan)",
            borderRadius: "6px",
            background: scanMut.isPending ? "var(--bg-elevated)" : "var(--cyan-dim)",
            color: scanMut.isPending ? "var(--text-muted)" : "var(--cyan)",
            cursor: scanMut.isPending ? "wait" : "pointer", transition: "all 0.15s",
          }}>
          <RefreshCw size={11} strokeWidth={2}
            style={{ animation: scanMut.isPending ? "spin 1s linear infinite" : "none" }} />
          {scanMut.isPending ? "scanning" : "scan now"}
        </button>
      </div>

      {/* Stat strip */}
      {!isLoading && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "8px" }}>
          {[
            { label: "total",    value: incidents.length,           accent: false },
            { label: "open",     value: openCount,                  accent: openCount > 0 },
            { label: "critical", value: critCount,                  accent: critCount > 0 },
            { label: "avg lat",  value: stats?.avg_latency_ms != null
                ? `${Math.round(stats.avg_latency_ms)}ms` : "—",   accent: false },
          ].map(({ label, value, accent }) => (
            <div key={label} style={{
              border: `0.5px solid ${accent ? "var(--red)" : "var(--border)"}`,
              borderRadius: "6px", padding: "10px 14px",
              background: accent ? "var(--red-dim)" : "var(--bg-surface)",
            }}>
              <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "9px",
                letterSpacing: "0.12em", textTransform: "uppercase",
                color: accent ? "var(--red)" : "var(--text-muted)" }}>{label}</div>
              <div style={{ fontFamily: "'Syne', sans-serif", fontSize: "20px", fontWeight: 700,
                color: accent ? "var(--red)" : "var(--text-primary)", marginTop: "4px",
                lineHeight: 1 }}>{value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Filter bar */}
      <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", alignItems: "center" }}>
        {FILTERS.map((f) => (
          <button key={f} onClick={() => setFilter(f)} style={{
            fontFamily: "'IBM Plex Mono', monospace", fontSize: "9px",
            letterSpacing: "0.1em", textTransform: "uppercase",
            padding: "5px 10px", borderRadius: "4px", cursor: "pointer", transition: "all 0.12s",
            border: filter === f ? "0.5px solid var(--cyan)" : "0.5px solid var(--border)",
            background: filter === f ? "var(--cyan-dim)" : "transparent",
            color: filter === f ? "var(--cyan)" : "var(--text-muted)",
          }}>{f}</button>
        ))}
        <span style={{ marginLeft: "auto", fontFamily: "'IBM Plex Mono', monospace",
          fontSize: "10px", color: "var(--text-muted)" }}>
          {filtered.length}/{incidents.length}
        </span>
      </div>

      {error && <ErrorBanner message="Failed to load incidents." />}

      {isLoading ? (
        <Skeleton rows={5} />
      ) : filtered.length === 0 ? (
        <EmptyState message="no incidents match filter" />
      ) : (
        <div style={{ position: "relative" }}>
          {/* Timeline spine */}
          <div style={{ position: "absolute", left: "7px", top: 0, bottom: 0,
            width: "1px", background: "var(--border)" }} />
          <div style={{ display: "flex", flexDirection: "column", gap: "0" }}>
            {filtered.map((inc, i) => (
              <IncidentRow key={inc.id} incident={inc} index={i} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function IncidentRow({ incident, index }: { incident: Incident; index: number }) {
  const [open, setOpen] = useState(false);

  const dotColor = SEV_GLOW[incident.severity] ?? "var(--text-muted)";

  const ts = (() => {
    try { return format(parseISO(incident.timestamp), "MMM dd HH:mm:ss"); }
    catch { return incident.timestamp; }
  })();

  return (
    <div style={{ position: "relative", paddingLeft: "24px", paddingBottom: "8px",
      animationDelay: `${index * 35}ms` }}>
      {/* Timeline dot */}
      <div style={{ position: "absolute", left: "0", top: "10px",
        width: "14px", height: "14px", borderRadius: "50%",
        background: dotColor,
        boxShadow: open ? `0 0 10px ${dotColor}` : "none",
        border: "2px solid var(--bg-base)",
        transition: "box-shadow 0.2s",
      }} />

      <div
        onClick={() => setOpen((o) => !o)}
        style={{
          border: `0.5px solid ${open ? "var(--border-strong)" : "var(--border)"}`,
          borderRadius: "6px", padding: "10px 14px", cursor: "pointer",
          background: open ? "var(--bg-elevated)" : "var(--bg-surface)",
          transition: "all 0.15s",
        }}
        onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--border-strong)"; }}
        onMouseLeave={(e) => { e.currentTarget.style.borderColor = open ? "var(--border-strong)" : "var(--border)"; }}
      >
        {/* Row header */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
          <SeverityBadge level={incident.severity} />
          <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
            color: "var(--text-muted)", display: "flex", alignItems: "center", gap: "4px" }}>
            <Clock size={10} strokeWidth={1.75} />
            {ts}
          </span>
          {incident.status === "resolved" && (
            <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "9px",
              letterSpacing: "0.1em", border: "0.5px solid var(--green)",
              color: "var(--green)", padding: "2px 6px", borderRadius: "3px" }}>
              resolved
            </span>
          )}
          <span style={{ marginLeft: "auto", color: "var(--text-muted)", fontSize: "11px" }}>
            {open ? "▲" : "▼"}
          </span>
        </div>

        {/* Title */}
        <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "13px",
          color: "var(--text-primary)", marginTop: "6px", lineHeight: 1.5 }}>
          {incident.title}
        </p>

        {/* Expanded */}
        {open && (
          <div style={{ marginTop: "10px", paddingTop: "10px",
            borderTop: "0.5px solid var(--border)", display: "flex",
            flexDirection: "column", gap: "8px", animation: "fadeIn 0.2s ease-out both" }}>
            <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "12px",
              color: "var(--text-secondary)", lineHeight: 1.6 }}>
              {incident.description}
            </p>
            <div style={{ display: "flex", gap: "16px" }}>
              <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "9px",
                color: "var(--text-muted)", display: "flex", alignItems: "center", gap: "4px" }}>
                <Hash size={9} />id: {incident.id}
              </span>
              {incident.source && (
                <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "9px",
                  color: "var(--text-muted)", display: "flex", alignItems: "center", gap: "4px" }}>
                  <Radio size={9} />source: {incident.source}
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
