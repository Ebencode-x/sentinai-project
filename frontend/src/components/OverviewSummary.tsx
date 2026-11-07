import type { ActivityReport } from "@/api/activity";
import StatCard from "@/components/StatCard";
import { RANGES, activeSourcesSince, compareText, windowTotals, type Range } from "@/lib/activity";

interface Props {
  report: ActivityReport | undefined;
  loading: boolean;
  error: boolean;
  openCount: number;
  range: Range;
  onRange: (range: Range) => void;
}

export default function OverviewSummary({ report, loading, error, openCount, range, onRange }: Props) {
  const ready = !!report && !loading;
  const daily = report?.daily ?? [];
  const current = windowTotals(daily, range);
  const previous = windowTotals(daily, range, 1);
  const sources = report?.sources ?? [];
  const configured = sources.filter((s) => s.status === "active").length;

  const value = (n: number) => (ready ? n.toLocaleString("en-US") : error ? "n/a" : "...");
  const compare = (cur: number, prev: number) =>
    ready ? compareText(cur, prev, range) : error ? "Could not load activity" : "Loading";

  return (
    <section className="flex flex-col gap-3" aria-label="Summary">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          Last {range} days
        </h2>
        <div className="flex items-center gap-4 text-xs" role="group" aria-label="Time range">
          {RANGES.map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => onRange(r)}
              aria-pressed={r === range}
              className={r === range ? "underline underline-offset-4" : ""}
              style={{
                color: r === range ? "var(--text-primary)" : "var(--text-muted)",
                fontWeight: r === range ? 600 : 400,
              }}
            >
              {r} days
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        <StatCard label="Open incidents" value={openCount} sub="Right now" />
        <StatCard
          label="New incidents"
          value={value(current.newIncidents)}
          sub={compare(current.newIncidents, previous.newIncidents)}
        />
        <StatCard
          label="Resolved"
          value={value(current.resolved)}
          sub={compare(current.resolved, previous.resolved)}
        />
        <StatCard
          label="Events received"
          value={value(current.events)}
          sub={compare(current.events, previous.events)}
        />
        <StatCard
          label="Active sources"
          value={value(activeSourcesSince(sources))}
          sub={ready ? `Last 24 hours, ${configured} configured` : compare(0, 0)}
        />
      </div>
    </section>
  );
}
