import { Fragment, useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { format, parseISO } from "date-fns";
import { ChevronRight, RefreshCw } from "lucide-react";
import { api } from "@/api/client";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/components/Toast";
import { Card } from "@/components/Card";
import StatCard from "@/components/StatCard";
import SeverityBadge from "@/components/SeverityBadge";

const SEV_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };

const FILTERS = [
  { key: "all", label: "All" },
  { key: "open", label: "Open" },
  { key: "resolved", label: "Resolved" },
  { key: "critical", label: "Critical" },
  { key: "high", label: "High" },
  { key: "medium", label: "Medium" },
  { key: "low", label: "Low" },
];

function fmt(ts: string): string {
  try {
    return format(parseISO(ts), "MMM d, HH:mm:ss");
  } catch {
    return ts;
  }
}

export default function IncidentTimeline() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const { user } = useAuth();
  const [filter, setFilter] = useState("all");
  const [openId, setOpenId] = useState<string | null>(null);

  const { data: incidents = [], isLoading, isError } = useQuery({
    queryKey: ["incidents"],
    queryFn: () => api.incidents().then((r) => r.data),
    refetchInterval: 15_000,
  });

  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: () => api.stats().then((r) => r.data),
    refetchInterval: 30_000,
  });

  const scanMut = useMutation({
    mutationFn: () => api.scanNow().then((r) => r.data),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["incidents"] });
      toast(
        data.detected_incidents > 0
          ? `Scan complete, ${data.detected_incidents} new`
          : "Scan complete, nothing new found",
        data.detected_incidents > 0 ? "warn" : "ok"
      );
    },
    onError: () => toast("Scan failed", "error"),
  });

  const rows = useMemo(() => {
    const sorted = [...incidents].sort(
      (a, b) =>
        (SEV_ORDER[a.severity] ?? 4) - (SEV_ORDER[b.severity] ?? 4) ||
        new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );
    return filter === "all" ? sorted : sorted.filter((i) => i.severity === filter || i.status === filter);
  }, [incidents, filter]);

  const critCount = incidents.filter((i) => i.severity === "critical").length;
  const openCount = incidents.filter((i) => i.status === "open").length;
  const avg = stats?.llm_metrics?.avg_latency_ms ?? stats?.avg_latency_ms ?? null;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Incidents</h1>
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            Detected from your logs, refreshed every 15 seconds
          </p>
        </div>
        {user?.role === "admin" && (
          <button
            onClick={() => scanMut.mutate()}
            disabled={scanMut.isPending}
            className="inline-flex items-center gap-2 rounded-md px-3.5 h-9 text-sm font-medium transition-opacity disabled:opacity-60"
            style={{ background: "var(--brand)", color: "#1a1a1a" }}
          >
            <RefreshCw size={14} className={scanMut.isPending ? "animate-spin" : ""} />
            {scanMut.isPending ? "Scanning" : "Scan now"}
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total" value={incidents.length} />
        <StatCard label="Open" value={openCount} />
        <StatCard label="Critical" value={critCount} accent={critCount > 0} color="red" />
        <StatCard label="Avg LLM latency" value={avg != null ? `${Math.round(avg)} ms` : "n/a"} />
      </div>

      <Card>
        <div className="flex flex-wrap items-center gap-2 px-4 py-3" style={{ borderBottom: "1px solid var(--border)" }}>
          <div className="flex flex-wrap gap-1">
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
          <span className="ml-auto text-xs" style={{ color: "var(--text-muted)" }}>
            {rows.length} of {incidents.length} incidents
          </span>
        </div>

        {isLoading ? (
          <div className="p-4 flex flex-col gap-2">
            {[0, 1, 2, 3, 4].map((i) => (
              <div key={i} className="h-10 rounded-md animate-pulse" style={{ background: "var(--bg-panel)" }} />
            ))}
          </div>
        ) : isError ? (
          <p className="p-8 text-sm text-center" style={{ color: "var(--red)" }}>
            Could not load incidents.
          </p>
        ) : rows.length === 0 ? (
          <p className="p-8 text-sm text-center" style={{ color: "var(--text-muted)" }}>
            {incidents.length === 0 ? "No incidents detected." : "No incidents match this filter."}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[620px]">
              <thead>
                <tr style={{ color: "var(--text-muted)" }}>
                  <th className="w-8" />
                  <th className="text-left font-medium text-xs px-2 py-2">Title</th>
                  <th className="text-left font-medium text-xs px-2 py-2 w-28">Severity</th>
                  <th className="text-left font-medium text-xs px-2 py-2 w-28">Status</th>
                  <th className="text-right font-medium text-xs px-4 py-2 w-40">Detected</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((inc) => {
                  const open = openId === inc.id;
                  return (
                    <Fragment key={inc.id}>
                      <tr
                        onClick={() => setOpenId(open ? null : inc.id)}
                        className="cursor-pointer transition-colors hover:bg-[var(--bg-panel)]"
                        style={{ borderTop: "1px solid var(--border)", background: open ? "var(--bg-panel)" : undefined }}
                      >
                        <td className="pl-3">
                          <ChevronRight
                            size={14}
                            className="transition-transform"
                            style={{ color: "var(--text-muted)", transform: open ? "rotate(90deg)" : undefined }}
                          />
                        </td>
                        <td className="px-2 py-3 max-w-0">
                          <p className="truncate font-medium">{inc.title}</p>
                          {inc.source && (
                            <p className="truncate text-xs" style={{ color: "var(--text-muted)" }}>{inc.source}</p>
                          )}
                        </td>
                        <td className="px-2 py-3"><SeverityBadge level={inc.severity} /></td>
                        <td className="px-2 py-3">
                          <span className="inline-flex items-center gap-2 text-xs" style={{ color: "var(--text-secondary)" }}>
                            <span
                              className="w-2 h-2 rounded-full"
                              style={{ background: inc.status === "open" ? "var(--amber)" : "var(--green)" }}
                            />
                            {inc.status === "open" ? "Open" : "Resolved"}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right text-xs" style={{ color: "var(--text-muted)" }}>
                          {fmt(inc.timestamp)}
                        </td>
                      </tr>
                      {open && (
                        <tr style={{ background: "var(--bg-base)" }}>
                          <td colSpan={5} className="px-4 py-4">
                            <p className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>Details</p>
                            <pre
                              className="text-xs rounded-md p-3 overflow-x-auto whitespace-pre-wrap break-words"
                              style={{
                                background: "var(--bg-panel)",
                                border: "1px solid var(--border)",
                                color: "var(--text-secondary)",
                                fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
                              }}
                            >
                              {inc.description}
                            </pre>
                            <p className="text-xs mt-3 break-all" style={{ color: "var(--text-muted)" }}>
                              ID: {inc.id}
                              {inc.source ? `  ·  Source: ${inc.source}` : ""}
                            </p>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
