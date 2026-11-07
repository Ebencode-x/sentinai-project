import { formatDistanceToNow, parseISO } from "date-fns";
import { Link } from "react-router";
import type { Incident } from "@/api/client";
import { Card, CardHeader } from "@/components/Card";

const MAX_ROWS = 5;

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

function seen(i: Incident): string {
  return i.last_seen ?? i.timestamp;
}

function millis(ts: string): number {
  const t = new Date(ts).getTime();
  return Number.isNaN(t) ? 0 : t;
}

function ago(ts: string): string {
  try {
    return formatDistanceToNow(parseISO(ts), { addSuffix: true });
  } catch {
    return ts;
  }
}

function Message({ text, sub }: { text: string; sub?: string }) {
  return (
    <div className="px-4 py-10 text-center">
      <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{text}</p>
      {sub && <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>{sub}</p>}
    </div>
  );
}

interface Props {
  incidents: Incident[];
  loading: boolean;
  error: boolean;
}

export default function NeedsAttention({ incidents, loading, error }: Props) {
  const open = incidents
    .filter((i) => i.status === "open")
    .sort(
      (a, b) =>
        (ORDER[a.severity] ?? 4) - (ORDER[b.severity] ?? 4) ||
        millis(seen(b)) - millis(seen(a)),
    );
  const shown = open.slice(0, MAX_ROWS);
  const more = open.length - shown.length;

  let body;
  if (error && incidents.length === 0) {
    body = <Message text="Could not load incidents" />;
  } else if (loading && incidents.length === 0) {
    body = <Message text="Loading" />;
  } else if (open.length === 0) {
    body =
      incidents.length === 0 ? (
        <Message text="No incidents yet" sub="Nothing has been detected so far." />
      ) : (
        <Message text="No open incidents" sub="Everything that was detected has been resolved." />
      );
  } else {
    body = (
      <ul>
        {shown.map((i, idx) => {
          const n = i.occurrences ?? 1;
          return (
            <li key={i.id} style={{ borderTop: idx === 0 ? undefined : "1px solid var(--border)" }}>
              <Link
                to={`/incidents?open=${encodeURIComponent(i.id)}`}
                className="flex items-center gap-4 px-4 py-3 text-sm hover:bg-[var(--bg-panel)]"
              >
                <span
                  className="w-16 shrink-0 text-xs font-medium"
                  style={{ color: COLOR[i.severity] ?? "var(--text-secondary)" }}
                >
                  {LABEL[i.severity] ?? i.severity}
                </span>
                <span className="flex-1 min-w-0 truncate" style={{ color: "var(--text-primary)" }}>
                  {i.title}
                </span>
                <span
                  className="hidden sm:flex items-center gap-4 text-xs tabular-nums shrink-0"
                  style={{ color: "var(--text-muted)" }}
                >
                  {i.source && <span>{i.source}</span>}
                  <span>{n} {n === 1 ? "time" : "times"}</span>
                </span>
                <span
                  className="w-28 shrink-0 text-right text-xs tabular-nums"
                  style={{ color: "var(--text-muted)" }}
                >
                  {ago(seen(i))}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    );
  }

  return (
    <Card>
      <CardHeader
        title="Needs attention"
        action={
          <Link to="/incidents" className="text-xs" style={{ color: "var(--text-muted)" }}>
            View all
          </Link>
        }
      />
      {body}
      {more > 0 && (
        <Link
          to="/incidents"
          className="block px-4 py-3 text-xs hover:bg-[var(--bg-panel)]"
          style={{ borderTop: "1px solid var(--border)", color: "var(--text-secondary)" }}
        >
          {more} more open {more === 1 ? "incident" : "incidents"}
        </Link>
      )}
    </Card>
  );
}
