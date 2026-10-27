import { useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { formatDistanceToNow, parseISO } from "date-fns";
import { Search } from "lucide-react";
import type { Incident } from "@/api/client";
import { Card, CardHeader } from "@/components/Card";
import SeverityBadge from "@/components/SeverityBadge";

type Filter = "all" | "open" | "critical";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "open", label: "Open" },
  { key: "critical", label: "Critical" },
];

function ago(ts: string): string {
  try {
    return formatDistanceToNow(parseISO(ts), { addSuffix: true });
  } catch {
    return ts;
  }
}

export default function IncidentsTable({
  incidents,
  loading,
}: {
  incidents: Incident[];
  loading: boolean;
}) {
  const navigate = useNavigate();
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return incidents
      .filter((i) =>
        filter === "all" ? true : filter === "open" ? i.status === "open" : i.severity === "critical"
      )
      .filter((i) => !q || i.title.toLowerCase().includes(q) || (i.source ?? "").toLowerCase().includes(q));
  }, [incidents, filter, query]);

  return (
    <Card>
      <CardHeader title="Incidents" />

      <div className="flex flex-wrap items-center gap-2 px-4 py-3" style={{ borderBottom: "1px solid var(--border)" }}>
        <div className="flex gap-1">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className="px-3 py-1 rounded-full text-xs font-medium transition-colors"
              style={{
                background: filter === f.key ? "var(--bg-hover)" : "transparent",
                color: filter === f.key ? "var(--text-primary)" : "var(--text-secondary)",
              }}
            >
              {f.label}
            </button>
          ))}
        </div>
        <div
          className="ml-auto flex items-center gap-2 rounded-md px-2.5 h-8 min-w-[180px]"
          style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}
        >
          <Search size={14} style={{ color: "var(--text-muted)" }} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search incidents"
            className="bg-transparent outline-none text-sm w-full"
            style={{ color: "var(--text-primary)" }}
          />
        </div>
      </div>

      {loading && incidents.length === 0 ? (
        <div className="p-4 flex flex-col gap-2">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-10 rounded-md animate-pulse" style={{ background: "var(--bg-panel)" }} />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <p className="p-8 text-sm text-center" style={{ color: "var(--text-muted)" }}>
          {incidents.length === 0 ? "No incidents detected." : "No incidents match this filter."}
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[560px]">
            <thead>
              <tr style={{ color: "var(--text-muted)" }}>
                <th className="text-left font-medium text-xs px-4 py-2 w-24">Status</th>
                <th className="text-left font-medium text-xs px-2 py-2">Title</th>
                <th className="text-left font-medium text-xs px-2 py-2 w-28">Severity</th>
                <th className="text-right font-medium text-xs px-4 py-2 w-36">Detected</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 8).map((i) => (
                <tr
                  key={i.id}
                  onClick={() => navigate("/incidents")}
                  className="cursor-pointer transition-colors hover:bg-[var(--bg-panel)]"
                  style={{ borderTop: "1px solid var(--border)" }}
                >
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-2 text-xs" style={{ color: "var(--text-secondary)" }}>
                      <span
                        className="w-2 h-2 rounded-full"
                        style={{ background: i.status === "open" ? "var(--amber)" : "var(--green)" }}
                      />
                      {i.status === "open" ? "Open" : "Resolved"}
                    </span>
                  </td>
                  <td className="px-2 py-3 max-w-0">
                    <p className="truncate font-medium" style={{ color: "var(--text-primary)" }}>{i.title}</p>
                    {i.source && (
                      <p className="truncate text-xs" style={{ color: "var(--text-muted)" }}>{i.source}</p>
                    )}
                  </td>
                  <td className="px-2 py-3"><SeverityBadge level={i.severity} /></td>
                  <td className="px-4 py-3 text-right text-xs" style={{ color: "var(--text-muted)" }}>
                    {ago(i.timestamp)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
