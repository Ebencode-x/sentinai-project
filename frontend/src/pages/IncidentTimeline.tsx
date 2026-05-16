import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type Incident } from "@/api/client";
import { format, parseISO } from "date-fns";
import SeverityBadge from "@/components/SeverityBadge";
import StatCard from "@/components/StatCard";
import Skeleton from "@/components/Skeleton";
import EmptyState from "@/components/EmptyState";
import ErrorBanner from "@/components/ErrorBanner";
import { useToast } from "@/components/Toast";
import clsx from "clsx";

function severityOrder(s: string) {
  return ({ critical: 0, high: 1, medium: 2, low: 3 } as Record<string,number>)[s] ?? 4;
}

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
      toast(
        `Scan complete — ${data.detected_incidents} incident(s) detected`,
        data.detected_incidents > 0 ? "warn" : "ok"
      );
    },
    onError: () => toast("Scan failed — check backend connection", "error"),
  });

  const sorted = [...incidents].sort(
    (a, b) =>
      severityOrder(a.severity) - severityOrder(b.severity) ||
      new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  );

  const filtered =
    filter === "all"
      ? sorted
      : sorted.filter((i) => i.severity === filter || i.status === filter);

  const critCount = incidents.filter((i) => i.severity === "critical").length;
  const openCount = incidents.filter((i) => i.status === "open").length;

  return (
    <div className="space-y-6 animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-sm font-display tracking-widest">INCIDENT TIMELINE</h1>
          <p className="text-xs text-muted mt-1 tracking-wide">
            Live feed — auto-refresh every 15s
          </p>
        </div>
        <button
          onClick={() => scanMut.mutate()}
          disabled={scanMut.isPending}
          className={clsx(
            "text-xs tracking-widest px-4 py-2 border rounded-sm transition-all",
            scanMut.isPending
              ? "text-muted border-bg-border cursor-wait"
              : "text-accent border-accent hover:bg-accent hover:text-bg hover:shadow-glow-accent"
          )}
        >
          {scanMut.isPending ? "SCANNING…" : "▷ SCAN NOW"}
        </button>
      </div>

      {/* Stats */}
      {isLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Skeleton className="h-20" rows={4} />
        </div>
      ) : stats ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard label="TOTAL SCANS" value={stats.total_suggestions} />
          <StatCard label="OPEN"        value={openCount} accent={openCount > 0} />
          <StatCard label="CRITICAL"    value={critCount} accent={critCount > 0} />
          <StatCard
            label="AVG LATENCY"
            value={stats.avg_latency_ms != null ? `${stats.avg_latency_ms}ms` : "—"}
            sub={stats.p95_latency_ms != null ? `p95: ${stats.p95_latency_ms}ms` : undefined}
          />
        </div>
      ) : null}

      {/* Filter bar */}
      <div className="flex gap-2 flex-wrap items-center">
        {["all","critical","high","medium","low","open","resolved"].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={clsx(
              "text-[10px] tracking-widest px-3 py-1 border rounded-sm uppercase transition-all",
              filter === f
                ? "border-accent text-accent bg-accent/5"
                : "border-bg-border text-muted hover:text-text hover:border-text/30"
            )}
          >
            {f}
          </button>
        ))}
        <span className="ml-auto text-xs text-muted">
          {filtered.length} / {incidents.length}
        </span>
      </div>

      {error && (
        <ErrorBanner message="Failed to load incidents. Verify API key and backend URL." />
      )}

      {isLoading ? (
        <Skeleton className="h-16" rows={5} />
      ) : filtered.length === 0 ? (
        <EmptyState message="NO INCIDENTS MATCH FILTER" />
      ) : (
        <div className="relative space-y-0">
          <div className="absolute left-[7px] top-0 bottom-0 w-px bg-bg-border" />
          {filtered.map((inc, i) => (
            <IncidentRow key={inc.id} incident={inc} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}

function IncidentRow({ incident, index }: { incident: Incident; index: number }) {
  const [open, setOpen] = useState(false);

  const dotColor =
    incident.severity === "critical" ? "bg-red-500 shadow-[0_0_8px_#ef4444]" :
    incident.severity === "high"     ? "bg-warn shadow-[0_0_8px_#ff6b35]"    :
    incident.severity === "medium"   ? "bg-yellow-500"                         :
    "bg-ok";

  const ts = (() => {
    try { return format(parseISO(incident.timestamp), "MMM dd HH:mm:ss"); }
    catch { return incident.timestamp; }
  })();

  return (
    <div
      className="relative pl-6 pb-4 cursor-pointer group"
      style={{ animationDelay: `${index * 40}ms` }}
      onClick={() => setOpen((o) => !o)}
    >
      <div className={clsx(
        "absolute left-0 top-1.5 w-3.5 h-3.5 rounded-full border-2 border-bg",
        dotColor
      )} />
      <div className={clsx(
        "border border-bg-border bg-bg-card px-4 py-3 rounded-sm transition-all",
        "group-hover:border-accent/30",
        open && "border-accent/20"
      )}>
        <div className="flex items-start gap-3 flex-wrap">
          <SeverityBadge level={incident.severity} />
          <span className="text-xs text-muted font-mono">{ts}</span>
          {incident.status === "resolved" && (
            <span className="text-[10px] text-ok tracking-widest border border-ok/30 px-1.5 py-0.5 rounded-sm">
              RESOLVED
            </span>
          )}
          <span className="ml-auto text-muted text-xs">{open ? "▲" : "▼"}</span>
        </div>
        <p className="text-sm text-text mt-2 leading-relaxed">{incident.title}</p>
        {open && (
          <div className="mt-3 pt-3 border-t border-bg-border space-y-2 animate-fade-in">
            <p className="text-xs text-muted leading-relaxed">{incident.description}</p>
            <div className="text-[10px] text-muted/60 tracking-wider font-mono">
              ID: {incident.id}
              {incident.source && ` · SOURCE: ${incident.source}`}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
