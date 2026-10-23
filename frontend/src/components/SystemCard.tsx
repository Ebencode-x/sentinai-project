import { formatDistanceToNow, parseISO } from "date-fns";
import type { StatsSnapshot } from "@/api/client";
import { Card, CardHeader } from "@/components/Card";

function ms(v: number | null | undefined): string {
  return v == null ? "n/a" : `${Math.round(v)} ms`;
}

function lastScan(ts: string | null | undefined): string {
  if (!ts) return "Never";
  try {
    return formatDistanceToNow(parseISO(ts), { addSuffix: true });
  } catch {
    return ts;
  }
}

export default function SystemCard({ stats }: { stats: StatsSnapshot | null }) {
  const m = stats?.llm_metrics;
  const rate = m?.fallback_rate ?? 0;
  const rows: [string, string][] = [
    ["LLM provider", stats?.llm_provider ?? "n/a"],
    ["Total scans", String(stats?.total_scan_runs ?? 0)],
    ["Last scan", lastScan(stats?.last_scan_at_utc)],
    ["Suggestions", String(m?.total_suggestions ?? 0)],
    ["Fallback rate", `${Math.round(rate * 100)}%`],
    ["Avg latency", ms(m?.avg_latency_ms)],
    ["p95 latency", ms(m?.p95_latency_ms)],
  ];

  return (
    <Card>
      <CardHeader title="System" />
      <dl>
        {rows.map(([k, v], i) => (
          <div
            key={k}
            className="flex items-center justify-between px-4 py-2.5 text-sm"
            style={{ borderTop: i === 0 ? undefined : "1px solid var(--border)" }}
          >
            <dt style={{ color: "var(--text-secondary)" }}>{k}</dt>
            <dd className="font-medium">{v}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}
