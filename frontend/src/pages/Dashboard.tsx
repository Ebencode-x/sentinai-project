import { useState } from "react";
import { RefreshCw } from "lucide-react";
import {
  useSentinaiStore,
  selectSortedIncidents,
  selectCriticalCount,
  selectOpenCount,
} from "@/store/sentinai";
import { useAuth } from "@/hooks/useAuth";
import StatCard from "@/components/StatCard";
import IncidentsTable from "@/components/IncidentsTable";
import SeverityDonut from "@/components/SeverityDonut";
import ActivityHeatmap from "@/components/ActivityHeatmap";
import ActivityFeed from "@/components/ActivityFeed";
import SystemCard from "@/components/SystemCard";

export default function Dashboard() {
  const { user } = useAuth();
  const incidents = useSentinaiStore(selectSortedIncidents);
  const incLoading = useSentinaiStore((s) => s.incidentsLoading);
  const stats = useSentinaiStore((s) => s.stats);
  const critCount = useSentinaiStore(selectCriticalCount);
  const openCount = useSentinaiStore(selectOpenCount);
  const scanning = useSentinaiStore((s) => s.scanning);
  const triggerScan = useSentinaiStore((s) => s.triggerScan);
  const [scanMsg, setScanMsg] = useState<string | null>(null);

  async function handleScan() {
    setScanMsg(null);
    try {
      const r = await triggerScan();
      setScanMsg(
        r.detected_incidents === 0
          ? "Scan complete, nothing new found"
          : `Scan complete, ${r.detected_incidents} new incident${r.detected_incidents === 1 ? "" : "s"}`
      );
    } catch {
      setScanMsg("Scan failed");
    }
  }

  const fallbackPct = Math.round((stats?.llm_metrics?.fallback_rate ?? 0) * 100);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Overview</h1>
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            Incidents, remediation activity and system health
          </p>
        </div>
        {user?.role === "admin" && (
          <div className="flex items-center gap-3">
            {scanMsg && (
              <span className="text-xs" style={{ color: "var(--text-secondary)" }}>{scanMsg}</span>
            )}
            <button
              onClick={handleScan}
              disabled={scanning}
              className="inline-flex items-center gap-2 rounded-md px-3.5 h-9 text-sm font-medium transition-opacity disabled:opacity-60"
              style={{ background: "var(--brand)", color: "#1a1a1a" }}
            >
              <RefreshCw size={14} className={scanning ? "animate-spin" : ""} />
              {scanning ? "Scanning" : "Scan now"}
            </button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Open incidents" value={openCount} />
        <StatCard label="Critical" value={critCount} accent={critCount > 0} color="red" />
        <StatCard label="Scan runs" value={stats?.total_scan_runs ?? 0} />
        <StatCard
          label="Fallback rate"
          value={`${fallbackPct}%`}
          accent={fallbackPct > 20}
          color="amber"
          sub="Share of suggestions that used the fallback"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <IncidentsTable incidents={incidents} loading={incLoading} />
        </div>
        <SeverityDonut incidents={incidents} />
      </div>

      <ActivityHeatmap />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 flex flex-col">
          <ActivityFeed />
        </div>
        <SystemCard stats={stats} />
      </div>
    </div>
  );
}
