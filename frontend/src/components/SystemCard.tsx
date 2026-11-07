import { format, formatDistanceToNow, parseISO } from "date-fns";
import type { StatsSnapshot } from "@/api/client";
import { Card, CardHeader } from "@/components/Card";

interface Row {
  label: string;
  value: string;
  tone?: "ok" | "bad";
  title?: string;
}

const TONE = { ok: "var(--green)", bad: "var(--red)" };

function lastScan(ts: string | null | undefined): { value: string; title?: string } {
  if (!ts) return { value: "Never" };
  try {
    const d = parseISO(ts);
    return {
      value: formatDistanceToNow(d, { addSuffix: true }),
      title: format(d, "MMM d, yyyy, HH:mm:ss"),
    };
  } catch {
    return { value: ts };
  }
}

function buildRows(stats: StatsSnapshot): Row[] {
  const pending = stats.events_pending;
  const failed = stats.events_failed;
  const scan = lastScan(stats.last_scan_at_utc);
  const errors = stats.persistence_errors ?? 0;

  const rows: Row[] = [
    {
      label: "Database",
      value:
        stats.database_reachable === undefined
          ? "n/a"
          : stats.database_reachable
            ? "Reachable"
            : "Unreachable",
      tone:
        stats.database_reachable === undefined
          ? undefined
          : stats.database_reachable
            ? "ok"
            : "bad",
    },
    {
      label: "Event queue",
      value:
        pending === undefined && failed === undefined
          ? "n/a"
          : `${pending ?? 0} pending, ${failed ?? 0} failed`,
      tone: (failed ?? 0) > 0 ? "bad" : undefined,
    },
    { label: "Last scan", value: scan.value, title: scan.title },
    { label: "Provider", value: stats.llm_provider ?? "n/a" },
  ];

  if (errors > 0) {
    rows.push({ label: "Persistence errors", value: String(errors), tone: "bad" });
  }
  return rows;
}

export default function SystemCard({ stats }: { stats: StatsSnapshot | null }) {
  const rows: Row[] = stats
    ? buildRows(stats)
    : ["Database", "Event queue", "Last scan", "Provider"].map((label) => ({
        label,
        value: "Loading",
      }));

  return (
    <Card>
      <CardHeader title="System" />
      <dl>
        {rows.map((r, i) => (
          <div
            key={r.label}
            className="flex items-center justify-between gap-4 px-4 py-2.5 text-sm"
            style={{ borderTop: i === 0 ? undefined : "1px solid var(--border)" }}
          >
            <dt style={{ color: "var(--text-secondary)" }}>{r.label}</dt>
            <dd
              className="font-medium tabular-nums text-right"
              title={r.title}
              style={{ color: r.tone ? TONE[r.tone] : "var(--text-primary)" }}
            >
              {r.value}
            </dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}
