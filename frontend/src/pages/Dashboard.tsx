import { useSentinaiStore, selectSortedIncidents, selectCriticalCount, selectOpenCount, selectResolvedCount } from "@/store/sentinai";
import type { Incident } from "@/api/client";
import { formatDistanceToNow, parseISO } from "date-fns";
import {
  AlertOctagon,
  Activity,
  ShieldCheck,
  TrendingUp,
  TrendingDown,
  Minus,
  ArrowRight,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

/* ── tiny helpers ────────────────────────────────────────────────────── */

function relativeTime(ts: string) {
  try { return formatDistanceToNow(parseISO(ts), { addSuffix: true }); }
  catch { return ts; }
}

/* ── sub-components ──────────────────────────────────────────────────── */

function MetricCard({
  label,
  value,
  delta,
  deltaDir,
  topColor,
  valueColor,
  sparkPoints,
}: {
  label:       string;
  value:       string | number;
  delta?:      string;
  deltaDir?:   "up" | "down" | "neutral";
  topColor:    string;
  valueColor:  string;
  sparkPoints?: string;
}) {
  const DeltaIcon =
    deltaDir === "up" ? TrendingUp : deltaDir === "down" ? TrendingDown : Minus;

  return (
    <div
      className="relative overflow-hidden rounded-lg flex flex-col gap-2 p-4"
      style={{
        background:  "var(--bg-surface)",
        border:      "0.5px solid var(--border)",
      }}
    >
      {/* top accent line */}
      <div
        className="absolute top-0 left-0 right-0 h-[2px] rounded-t-lg"
        style={{ background: topColor }}
      />

      <p
        className="text-[10px] font-mono tracking-widest uppercase mt-1"
        style={{ color: "var(--text-muted)", fontFamily: "'IBM Plex Mono', monospace" }}
      >
        {label}
      </p>

      <p
        className="text-3xl font-display font-bold leading-none tracking-tight"
        style={{ color: valueColor, fontFamily: "'Syne', sans-serif" }}
      >
        {value}
      </p>

      {delta && (
        <div
          className="flex items-center gap-1 text-[11px] font-mono"
          style={{
            color:
              deltaDir === "up"
                ? "var(--red)"
                : deltaDir === "down"
                ? "var(--green)"
                : "var(--text-muted)",
            fontFamily: "'IBM Plex Mono', monospace",
          }}
        >
          <DeltaIcon size={11} strokeWidth={2} />
          {delta}
        </div>
      )}

      {/* sparkline */}
      {sparkPoints && (
        <svg
          viewBox="0 0 64 32"
          width="64"
          height="32"
          className="absolute bottom-0 right-0 opacity-20"
          preserveAspectRatio="none"
        >
          <polyline
            points={sparkPoints}
            fill="none"
            stroke={topColor}
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      )}
    </div>
  );
}

/* severity bar + row */
const SEV_COLORS: Record<string, string> = {
  critical: "var(--red)",
  high:     "var(--amber)",
  medium:   "var(--purple)",
  low:      "var(--cyan)",
};

const SEV_BG: Record<string, string> = {
  critical: "var(--red-dim)",
  high:     "var(--amber-dim)",
  medium:   "var(--purple-dim)",
  low:      "var(--cyan-dim)",
};

function IncidentRow({ inc }: { inc: Incident }) {
  const color  = SEV_COLORS[inc.severity] ?? "var(--text-muted)";
  const bgTag  = SEV_BG[inc.severity]    ?? "var(--bg-hover)";
  const resolved = inc.status === "resolved";

  return (
    <div
      className="flex items-start gap-3 px-4 py-3 transition-colors"
      style={{ borderBottom: "0.5px solid var(--border)" }}
      onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-elevated)")}
      onMouseLeave={(e) => (e.currentTarget.style.background = "")}
    >
      {/* severity bar */}
      <div
        className="w-[3px] self-stretch rounded-full shrink-0 mt-0.5"
        style={{ background: resolved ? "var(--green)" : color }}
      />

      <div className="flex-1 min-w-0">
        <p
          className="text-xs font-mono truncate font-medium"
          style={{ color: "var(--text-primary)", fontFamily: "'IBM Plex Mono', monospace" }}
        >
          {inc.title}
        </p>
        <div
          className="flex items-center gap-2 mt-1 text-[10px] font-mono"
          style={{ color: "var(--text-muted)", fontFamily: "'IBM Plex Mono', monospace" }}
        >
          <span
            className="px-1.5 py-0.5 rounded text-[9px] font-medium tracking-wider uppercase"
            style={{ background: resolved ? "var(--green-dim)" : bgTag, color: resolved ? "var(--green)" : color }}
          >
            {resolved ? "resolved" : inc.severity}
          </span>
          {inc.source && <span>{inc.source}</span>}
        </div>
      </div>

      <span
        className="text-[10px] font-mono shrink-0"
        style={{ color: "var(--text-muted)", fontFamily: "'IBM Plex Mono', monospace" }}
      >
        {relativeTime(inc.timestamp)}
      </span>
    </div>
  );
}

/* bar chart */
function BarChart({ incidents }: { incidents: import("@/api/client").Incident[] }) {
  const sevOrder = ["critical","high","medium","low"];
  const counts = sevOrder.map((sev) => incidents.filter((i) => i.severity === sev).length);
  const total  = counts.reduce((a, b) => a + b, 0);
  const barMax = Math.max(...counts, 1);

  const SEV_COLORS_BAR = ["var(--red)","var(--amber)","var(--purple)","var(--cyan)"];

  return (
    <div style={{ padding: "10px 16px 12px" }}>
      <p style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "9px",
        letterSpacing: "0.12em", textTransform: "uppercase",
        color: "var(--text-muted)", marginBottom: "10px" }}>
        incidents by severity{total > 0 ? ` · ${total} total` : " · no data"}
      </p>
      <div style={{ display: "flex", alignItems: "flex-end", gap: "6px", height: "52px" }}>
        {sevOrder.map((sev, i) => {
          const pct = (counts[i] / barMax) * 100;
          return (
            <div key={sev} style={{ flex: 1, display: "flex", flexDirection: "column",
              alignItems: "center", gap: "4px", height: "100%" }}>
              <div style={{ width: "100%", flex: 1, display: "flex", alignItems: "flex-end" }}>
                <div style={{ width: "100%", height: `${Math.max(pct, counts[i] > 0 ? 8 : 3)}%`,
                  background: counts[i] > 0 ? SEV_COLORS_BAR[i] : "var(--border)",
                  borderRadius: "2px 2px 0 0", transition: "height 0.4s ease",
                  minHeight: "3px" }} />
              </div>
              <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "8px",
                color: counts[i] > 0 ? SEV_COLORS_BAR[i] : "var(--text-muted)" }}>
                {sev.slice(0,4)}
              </span>
            </div>
          );
        })}
      </div>
      <div style={{ display: "flex", gap: "10px", marginTop: "8px", paddingTop: "8px",
        borderTop: "0.5px solid var(--border)" }}>
        {sevOrder.map((sev, i) => (
          <div key={sev} style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <div style={{ width: "6px", height: "6px", borderRadius: "50%",
              background: SEV_COLORS_BAR[i] }} />
            <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "9px",
              color: "var(--text-muted)" }}>{sev} · {counts[i]}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* rule coverage */
function RuleCoverage({ stats }: { stats: import("@/api/client").StatsSnapshot | null }) {
  const m = stats?.llm_metrics;
  const src = stats?.recent_suggestions_by_source;

  const total    = (src?.stub ?? 0) + (src?.provider ?? 0) + (src?.fallback ?? 0);
  const provider = src?.provider ?? 0;
  const fallback = src?.fallback ?? 0;
  const stub     = src?.stub ?? 0;

  const providerPct = total > 0 ? Math.round((provider / total) * 100) : 0;
  const fallbackPct = total > 0 ? Math.round((fallback / total) * 100) : 0;
  const stubPct     = total > 0 ? Math.round((stub     / total) * 100) : 0;
  const scanPct     = Math.min(100, (stats?.total_scan_runs ?? 0));

  const rows = [
    { label: "provider responses", pct: providerPct, color: "var(--green)"  },
    { label: "stub responses",     pct: stubPct,     color: "var(--cyan)"   },
    { label: "fallback rate",      pct: fallbackPct, color: fallbackPct > 20 ? "var(--red)" : "var(--amber)" },
    { label: "scan runs",          pct: Math.min(scanPct, 100),
      color: (stats?.total_scan_runs ?? 0) > 0 ? "var(--green)" : "var(--text-muted)",
      label2: String(stats?.total_scan_runs ?? 0) },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "10px", padding: "4px 16px 16px" }}>
      {m && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px",
          marginBottom: "4px" }}>
          {[
            { k: "avg latency", v: m.avg_latency_ms != null ? `${Math.round(m.avg_latency_ms)}ms` : "—" },
            { k: "p95",         v: m.p95_latency_ms != null ? `${Math.round(m.p95_latency_ms)}ms` : "—" },
            { k: "samples",     v: String(m.latency_sample_count) },
            { k: "fallbacks",   v: String(m.total_fallbacks) },
          ].map(({ k, v }) => (
            <div key={k} style={{ background: "var(--bg-base)", borderRadius: "4px",
              padding: "6px 8px", border: "0.5px solid var(--border)" }}>
              <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "8px",
                letterSpacing: "0.1em", color: "var(--text-muted)", textTransform: "uppercase" }}>{k}</div>
              <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "12px",
                color: "var(--text-primary)", marginTop: "2px" }}>{v}</div>
            </div>
          ))}
        </div>
      )}
      {rows.map(({ label, pct, color, label2 }) => (
        <div key={label}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
            <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
              color: "var(--text-secondary)" }}>{label}</span>
            <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
              color, fontWeight: 500 }}>{label2 ?? `${pct}%`}</span>
          </div>
          <div style={{ height: "3px", borderRadius: "2px", background: "var(--bg-elevated)" }}>
            <div style={{ height: "100%", width: `${pct}%`, background: color,
              borderRadius: "2px", transition: "width 0.4s ease" }} />
          </div>
        </div>
      ))}
    </div>
  );
}

/* uptime strip — 90 days */
function UptimeStrip({ stats }: { stats: import("@/api/client").StatsSnapshot | null }) {
  const scanRuns  = stats?.total_scan_runs ?? 0;
  const lastScan  = stats?.last_scan_at_utc;
  const provider  = stats?.llm_provider ?? "—";
  const fallRate  = stats?.llm_metrics?.fallback_rate ?? 0;
  const upColor   = fallRate > 0.3 ? "var(--red)" : fallRate > 0.1 ? "var(--amber)" : "var(--green)";
  const upLabel   = fallRate > 0.3 ? "degraded" : fallRate > 0.1 ? "partial" : "nominal";

  const lastScanLabel = (() => {
    if (!lastScan) return "never";
    try {
      const d = new Date(lastScan);
      const diff = Math.floor((Date.now() - d.getTime()) / 1000);
      if (diff < 60)   return `${diff}s ago`;
      if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
      return `${Math.floor(diff/3600)}h ago`;
    } catch { return lastScan; }
  })();

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "16px", padding: "10px 16px",
      borderRadius: "6px", background: "var(--bg-surface)", border: "0.5px solid var(--border)",
      flexWrap: "wrap" }}>
      {[
        { label: "system status", value: upLabel,        color: upColor },
        { label: "llm provider",  value: provider,       color: "var(--cyan)" },
        { label: "scan runs",     value: String(scanRuns), color: "var(--text-primary)" },
        { label: "last scan",     value: lastScanLabel,  color: "var(--text-secondary)" },
        { label: "fallback rate", value: `${(fallRate * 100).toFixed(1)}%`,
          color: fallRate > 0.2 ? "var(--amber)" : "var(--green)" },
      ].map(({ label, value, color }, i, arr) => (
        <div key={label} style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <div>
            <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "8px",
              letterSpacing: "0.12em", textTransform: "uppercase",
              color: "var(--text-muted)" }}>{label}</div>
            <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "12px",
              color, marginTop: "2px", fontWeight: 500 }}>{value}</div>
          </div>
          {i < arr.length - 1 && (
            <div style={{ width: "1px", height: "28px", background: "var(--border)",
              flexShrink: 0 }} />
          )}
        </div>
      ))}
    </div>
  );
}

/* ── Main component ──────────────────────────────────────────────────── */

export default function Dashboard() {
  const navigate = useNavigate();

  const incLoading    = useSentinaiStore((s) => s.incidentsLoading);
  const stats         = useSentinaiStore((s) => s.stats);
  const sorted        = useSentinaiStore(selectSortedIncidents);
  const critCount     = useSentinaiStore(selectCriticalCount);
  const openCount     = useSentinaiStore(selectOpenCount);
  const resolvedToday = useSentinaiStore(selectResolvedCount);

  return (
    <div className="flex flex-col gap-3 animate-slide-up max-w-[1200px]">

      {/* ── Metric row ─────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <MetricCard
          label="Critical"
          value={incLoading ? "—" : critCount}
          delta="+2 vs yesterday"
          deltaDir="up"
          topColor="var(--red)"
          valueColor="var(--red)"
          sparkPoints="0,28 10,26 20,22 30,26 40,16 50,20 64,6"
        />
        <MetricCard
          label="Open incidents"
          value={incLoading ? "—" : openCount}
          delta="+5 this week"
          deltaDir="up"
          topColor="var(--amber)"
          valueColor="var(--amber)"
          sparkPoints="0,18 10,20 20,16 30,14 40,18 50,12 64,8"
        />
        <MetricCard
          label="Resolved 24h"
          value={incLoading ? "—" : resolvedToday}
          delta={stats?.avg_latency_ms != null ? `MTTR ${stats.avg_latency_ms}ms` : "MTTR —"}
          deltaDir="down"
          topColor="var(--green)"
          valueColor="var(--green)"
          sparkPoints="0,26 10,22 20,18 30,14 40,12 50,8 64,4"
        />
        <MetricCard
          label="Policy violations"
          value={stats?.total_suggestions ?? "—"}
          delta="stable"
          deltaDir="neutral"
          topColor="var(--cyan)"
          valueColor="var(--cyan)"
          sparkPoints="0,16 10,14 20,18 30,15 40,17 50,13 64,15"
        />
      </div>

      {/* ── Two-column body ────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-3">

        {/* Left — incidents panel */}
        <div
          className="rounded-lg overflow-hidden flex flex-col"
          style={{ background: "var(--bg-surface)", border: "0.5px solid var(--border)" }}
        >
          {/* panel header */}
          <div
            className="flex items-center gap-2 px-4 py-3"
            style={{ borderBottom: "0.5px solid var(--border)" }}
          >
            <AlertOctagon size={14} style={{ color: "var(--red)" }} />
            <span
              className="text-[11px] font-mono font-medium tracking-widest uppercase"
              style={{ color: "var(--text-secondary)", fontFamily: "'IBM Plex Mono', monospace" }}
            >
              Active incidents
            </span>
            <span
              className="ml-auto text-[11px] font-mono"
              style={{ color: "var(--text-muted)", fontFamily: "'IBM Plex Mono', monospace" }}
            >
              {openCount} open
            </span>
            <button
              onClick={() => navigate("/incidents")}
              className="flex items-center gap-1 text-[10px] font-mono px-2 py-1 rounded transition-colors"
              style={{
                color:   "var(--cyan)",
                background: "var(--cyan-dim)",
                fontFamily: "'IBM Plex Mono', monospace",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--cyan-glow)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "var(--cyan-dim)")}
            >
              View all <ArrowRight size={10} />
            </button>
          </div>

          {/* incident rows */}
          <div className="flex-1">
            {incLoading ? (
              <div className="p-4 flex flex-col gap-2">
                {[1,2,3,4].map((i) => (
                  <div
                    key={i}
                    className="h-10 rounded animate-pulse"
                    style={{ background: "var(--bg-elevated)" }}
                  />
                ))}
              </div>
            ) : sorted.length === 0 ? (
              <div className="p-8 text-center">
                <p className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>
                  No incidents
                </p>
              </div>
            ) : (
              sorted.slice(0, 6).map((inc) => (
                <IncidentRow key={inc.id} inc={inc} />
              ))
            )}
          </div>

          {/* bar chart */}
          <div style={{ borderTop: "0.5px solid var(--border)" }}>
            <BarChart incidents={sorted} />
          </div>
        </div>

        {/* Right column */}
        <div className="flex flex-col gap-3">

          {/* Audit feed */}
          <div
            className="rounded-lg overflow-hidden flex-1"
            style={{ background: "var(--bg-surface)", border: "0.5px solid var(--border)" }}
          >
            <div
              className="flex items-center gap-2 px-4 py-3"
              style={{ borderBottom: "0.5px solid var(--border)" }}
            >
              <Activity size={14} style={{ color: "var(--cyan)" }} />
              <span
                className="text-[11px] font-mono font-medium tracking-widest uppercase"
                style={{ color: "var(--text-secondary)", fontFamily: "'IBM Plex Mono', monospace" }}
              >
                Audit feed
              </span>
            </div>
            {[
              { color: "var(--red)",    text: "D1 validator flagged", hi: "AUTH001", tail: "on PTH-0041",         time: "2m"  },
              { color: "var(--green)",  text: "Policy engine approved", hi: "PTH-0038", tail: " — 6/6 passed",   time: "14m" },
              { color: "var(--amber)",  text: "Rate limiter blocked", hi: "423 reqs",  tail: " from 10.0.0.41",  time: "31m" },
              { color: "var(--purple)", text: "EB reviewed diff for", hi: "PTH-0035",  tail: " — escalated",     time: "1h"  },
              { color: "var(--green)",  text: "Webhook dispatched to", hi: "#security-ops", tail: "",            time: "1h"  },
              { color: "var(--cyan)",   text: "CI", hi: "#86",           tail: " passed — 686 tests green",      time: "3h"  },
            ].map(({ color, text, hi, tail, time }, i) => (
              <div
                key={i}
                className="flex items-start gap-2.5 px-4 py-2.5"
                style={{ borderBottom: i < 5 ? "0.5px solid var(--border)" : undefined }}
              >
                <div
                  className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0"
                  style={{ background: color }}
                />
                <p
                  className="flex-1 text-[11px] leading-relaxed font-body"
                  style={{ color: "var(--text-secondary)", fontFamily: "'DM Sans', sans-serif" }}
                >
                  {text}{" "}
                  <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>{hi}</span>
                  {tail}
                </p>
                <span
                  className="text-[10px] font-mono shrink-0 mt-0.5"
                  style={{ color: "var(--text-muted)", fontFamily: "'IBM Plex Mono', monospace" }}
                >
                  {time}
                </span>
              </div>
            ))}
          </div>

          {/* Rule coverage */}
          <div
            className="rounded-lg overflow-hidden"
            style={{ background: "var(--bg-surface)", border: "0.5px solid var(--border)" }}
          >
            <div
              className="flex items-center gap-2 px-4 py-3"
              style={{ borderBottom: "0.5px solid var(--border)" }}
            >
              <ShieldCheck size={14} style={{ color: "var(--green)" }} />
              <span
                className="text-[11px] font-mono font-medium tracking-widest uppercase"
                style={{ color: "var(--text-secondary)", fontFamily: "'IBM Plex Mono', monospace" }}
              >
                Rule coverage
              </span>
            </div>
            <div className="pt-3">
              <RuleCoverage stats={stats} />
            </div>
          </div>
        </div>
      </div>

      {/* ── Uptime strip ───────────────────────────────── */}
      <UptimeStrip stats={stats} />
    </div>
  );
}
