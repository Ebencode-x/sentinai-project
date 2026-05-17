import { useQuery } from "@tanstack/react-query";
import { api, type Incident } from "@/api/client";
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
import clsx from "clsx";

/* ── tiny helpers ────────────────────────────────────────────────────── */

function relativeTime(ts: string) {
  try { return formatDistanceToNow(parseISO(ts), { addSuffix: true }); }
  catch { return ts; }
}

function severityOrder(s: string) {
  return ({ critical: 0, high: 1, medium: 2, low: 3 } as Record<string, number>)[s] ?? 4;
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
const HOURS = ["00","02","04","06","08","10","12","14","16","18","20","22"];
const MOCK_BARS = [4,2,2,3,7,10,8,6,13,9,5,3];
const BAR_MAX   = Math.max(...MOCK_BARS);

function BarChart() {
  return (
    <div className="px-4 pb-3">
      <p
        className="text-[9px] font-mono tracking-widest uppercase mb-2"
        style={{ color: "var(--text-muted)", fontFamily: "'IBM Plex Mono', monospace" }}
      >
        Incidents / 24h
      </p>
      <div className="flex items-end gap-1" style={{ height: "56px" }}>
        {MOCK_BARS.map((v, i) => {
          const pct = (v / BAR_MAX) * 100;
          const bg  = v >= 10 ? "var(--red)" : v >= 6 ? "var(--amber)" : "var(--cyan)";
          return (
            <div key={i} className="flex-1 flex flex-col items-center gap-1">
              <div
                className="w-full rounded-t-[2px] transition-all"
                style={{ height: `${pct}%`, background: bg, minHeight: "3px" }}
              />
              <span
                className="text-[8px] font-mono"
                style={{ color: "var(--text-hint)", fontFamily: "'IBM Plex Mono', monospace" }}
              >
                {HOURS[i]}
              </span>
            </div>
          );
        })}
      </div>
      <div className="flex gap-3 mt-2 pt-2" style={{ borderTop: "0.5px solid var(--border)" }}>
        {[
          { color: "var(--red)",   label: "critical/high" },
          { color: "var(--amber)", label: "medium"        },
          { color: "var(--cyan)",  label: "low"           },
        ].map(({ color, label }) => (
          <div key={label} className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full" style={{ background: color }} />
            <span
              className="text-[9px] font-mono"
              style={{ color: "var(--text-muted)", fontFamily: "'IBM Plex Mono', monospace" }}
            >
              {label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* rule coverage */
const RULES = [
  { label: "AUTH001–007", pct: 100, color: "var(--green)"  },
  { label: "PRIV001–003", pct: 100, color: "var(--green)"  },
  { label: "SEC001–002",  pct: 100, color: "var(--cyan)"   },
  { label: "TAINT001–002",pct:  67, color: "var(--amber)"  },
];

function RuleCoverage() {
  return (
    <div className="flex flex-col gap-2.5 px-4 pb-4">
      {RULES.map(({ label, pct, color }) => (
        <div key={label}>
          <div className="flex justify-between mb-1">
            <span
              className="text-[10px] font-mono"
              style={{ color: "var(--text-secondary)", fontFamily: "'IBM Plex Mono', monospace" }}
            >
              {label}
            </span>
            <span
              className="text-[10px] font-mono font-medium"
              style={{ color, fontFamily: "'IBM Plex Mono', monospace" }}
            >
              {pct}%
            </span>
          </div>
          <div
            className="h-[3px] rounded-full"
            style={{ background: "var(--bg-elevated)" }}
          >
            <div
              className="h-full rounded-full transition-all"
              style={{ width: `${pct}%`, background: color }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

/* uptime strip — 90 days */
const UPTIME_DAYS = Array.from({ length: 90 }, (_, i) => {
  if ([12, 43, 67].includes(i)) return "red";
  if ([20, 55, 71].includes(i)) return "amber";
  return "green";
});

function UptimeStrip() {
  return (
    <div
      className="flex items-center gap-3 px-4 py-3 rounded-lg"
      style={{ background: "var(--bg-surface)", border: "0.5px solid var(--border)" }}
    >
      <span
        className="text-[9px] font-mono tracking-widest uppercase shrink-0"
        style={{ color: "var(--text-muted)", fontFamily: "'IBM Plex Mono', monospace" }}
      >
        Uptime / 90d
      </span>
      <div className="flex gap-[2px] flex-1">
        {UPTIME_DAYS.map((c, i) => (
          <div
            key={i}
            className="flex-1 rounded-[2px]"
            style={{
              height: "16px",
              background:
                c === "green" ? "var(--green)"
                : c === "amber" ? "var(--amber)"
                : "var(--red)",
              opacity: 0.8,
            }}
          />
        ))}
      </div>
      <span
        className="text-sm font-mono font-medium shrink-0"
        style={{ color: "var(--green)", fontFamily: "'IBM Plex Mono', monospace" }}
      >
        99.3%
      </span>
    </div>
  );
}

/* ── Main component ──────────────────────────────────────────────────── */

export default function Dashboard() {
  const navigate = useNavigate();

  const { data: incidents = [], isLoading: incLoading } = useQuery({
    queryKey:       ["incidents"],
    queryFn:        () => api.incidents().then((r) => r.data),
    refetchInterval: 15_000,
  });

  const { data: stats } = useQuery({
    queryKey:       ["stats"],
    queryFn:        () => api.stats().then((r) => r.data),
    refetchInterval: 30_000,
  });

  /* derived */
  const sorted = [...incidents].sort(
    (a, b) =>
      severityOrder(a.severity) - severityOrder(b.severity) ||
      new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  );

  const critCount     = incidents.filter((i) => i.severity === "critical").length;
  const openCount     = incidents.filter((i) => i.status === "open").length;
  const resolvedToday = incidents.filter((i) => i.status === "resolved").length;

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
            <BarChart />
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
              <RuleCoverage />
            </div>
          </div>
        </div>
      </div>

      {/* ── Uptime strip ───────────────────────────────── */}
      <UptimeStrip />
    </div>
  );
}
