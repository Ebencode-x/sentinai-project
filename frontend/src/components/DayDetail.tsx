import { Link } from "react-router";
import { Card, CardHeader } from "@/components/Card";
import { dayLabel, utcDay } from "@/lib/activity";
import type { ActivityReport } from "@/api/activity";
import type { Incident } from "@/api/client";

const MAX_ROWS = 10;

const ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };
const COLOR: Record<string, string> = {
  critical: "var(--red)",
  high: "var(--amber)",
  medium: "var(--text-secondary)",
  low: "var(--green)",
};
const LABEL: Record<string, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
};

function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

function bySeverity(a: Incident, b: Incident): number {
  return (ORDER[a.severity] ?? 4) - (ORDER[b.severity] ?? 4) || b.timestamp.localeCompare(a.timestamp);
}

function Count({ value, label }: { value: number; label: string }) {
  return (
    <div>
      <div className="text-xl font-semibold tabular-nums">{value}</div>
      <div className="text-xs" style={{ color: "var(--text-muted)" }}>
        {label}
      </div>
    </div>
  );
}

function IncidentGroup({ title, items }: { title: string; items: Incident[] }) {
  if (items.length === 0) return null;
  const shown = items.slice(0, MAX_ROWS);
  const more = items.length - shown.length;
  return (
    <div style={{ borderTop: "1px solid var(--border)" }}>
      <h3 className="px-4 pt-3 text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
        {title}
      </h3>
      <ul className="py-1">
        {shown.map((i) => (
          <li key={i.id}>
            <Link
              to={`/incidents?open=${encodeURIComponent(i.id)}`}
              className="flex items-center gap-4 px-4 py-2 text-sm hover:bg-[var(--bg-panel)]"
            >
              <span
                className="w-16 shrink-0 text-xs font-medium"
                style={{ color: COLOR[i.severity] ?? "var(--text-secondary)" }}
              >
                {LABEL[i.severity] ?? i.severity}
              </span>
              <span className="min-w-0 flex-1 truncate">{i.title}</span>
              {i.source && (
                <span className="hidden shrink-0 text-xs sm:inline" style={{ color: "var(--text-muted)" }}>
                  {i.source}
                </span>
              )}
            </Link>
          </li>
        ))}
      </ul>
      {more > 0 && (
        <Link
          to="/incidents"
          className="block px-4 pb-3 text-xs hover:underline"
          style={{ color: "var(--text-secondary)" }}
        >
          {more} more, view all incidents
        </Link>
      )}
    </div>
  );
}

interface Props {
  report: ActivityReport | undefined;
  date: string | null;
  incidents: Incident[];
  onClose: () => void;
}

export default function DayDetail({ report, date, incidents, onClose }: Props) {
  if (!report || !date) return null;
  const index = report.daily.findIndex((d) => d.date === date);
  if (index < 0) return null;
  const day = report.daily[index];

  const opened = incidents.filter((i) => utcDay(i.timestamp) === date).sort(bySeverity);
  const resolved = incidents.filter((i) => utcDay(i.resolved_at) === date).sort(bySeverity);
  const incomplete = opened.length < day.new_incidents || resolved.length < day.resolved;

  // Per source counts only cover the last few days, aligned to the end of the report.
  const windowDays = report.sources.length > 0 ? report.sources[0].daily.length : 0;
  const slot = index - (report.daily.length - windowDays);
  const inWindow = windowDays > 0 && slot >= 0;
  const rows = inWindow
    ? report.sources
        .map((s) => ({ source: s, count: s.daily[slot] ?? 0 }))
        .filter((r) => r.count > 0)
    : [];
  const quiet = day.events === 0 && day.new_incidents === 0 && day.resolved === 0;

  return (
    <Card>
      <CardHeader
        title={dayLabel(date)}
        action={
          <button
            type="button"
            onClick={onClose}
            className="text-xs hover:underline"
            style={{ color: "var(--text-secondary)" }}
          >
            Clear
          </button>
        }
      />
      <div className="flex flex-wrap gap-x-10 gap-y-3 p-4">
        <Count value={day.events} label={day.events === 1 ? "event" : "events"} />
        <Count value={day.new_incidents} label={day.new_incidents === 1 ? "new incident" : "new incidents"} />
        <Count value={day.resolved} label="resolved" />
      </div>
      {quiet && (
        <p className="px-4 pb-4 text-sm" style={{ color: "var(--text-muted)" }}>
          No activity on this day.
        </p>
      )}
      {rows.length > 0 && (
        <div style={{ borderTop: "1px solid var(--border)" }}>
          <h3 className="px-4 pt-3 text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
            Events by source
          </h3>
          <ul className="py-1">
            {rows.map(({ source, count }) => (
              <li key={source.id} className="flex items-center justify-between gap-4 px-4 py-1.5 text-sm">
                <span className="min-w-0 truncate">
                  {source.name}
                  {source.status === "revoked" ? " (revoked)" : ""}
                </span>
                <span className="shrink-0 text-xs tabular-nums" style={{ color: "var(--text-muted)" }}>
                  {plural(count, "event")}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {day.events > 0 && windowDays > 0 && !inWindow && (
        <p className="px-4 pb-3 text-xs" style={{ color: "var(--text-muted)" }}>
          Counts per source are kept for the last {windowDays} days.
        </p>
      )}
      <IncidentGroup title="New incidents" items={opened} />
      <IncidentGroup title="Resolved" items={resolved} />
      {incomplete && (
        <p className="px-4 pb-3 text-xs" style={{ color: "var(--text-muted)" }}>
          Some incidents of this day are not in the loaded list. Open Incidents for the full history.
        </p>
      )}
    </Card>
  );
}
