import { useEffect } from "react";
import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { useApiKey } from "@/hooks/useApiKey";
import { useHealth } from "@/hooks/useHealth";
import { useToast } from "@/components/Toast";
import clsx from "clsx";

const NAV = [
  { to: "/incidents", label: "INCIDENTS", icon: "▲" },
  { to: "/audit",     label: "AUDIT",     icon: "≡" },
  { to: "/policy",    label: "POLICY",    icon: "◈" },
  { to: "/diff",      label: "DIFF",      icon: "±" },
];

export default function Layout() {
  const { clearKey } = useApiKey();
  const navigate     = useNavigate();
  const { live, ready, isBackendUp } = useHealth();
  const { toast } = useToast();

  // Notify once when backend goes down
  useEffect(() => {
    if (isBackendUp === false) {  // null = loading, false = confirmed down
      toast("Backend unreachable — check VITE_API_URL and backend status", "error");
    }
  }, [isBackendUp, toast]);

  const statusColor =
    ready?.status === "ok"       ? "text-ok"   :
    ready?.status === "degraded" ? "text-warn"  : "text-red-500";

  function handleLogout() {
    clearKey();
    navigate("/");
  }

  return (
    <div className="min-h-screen flex flex-col bg-bg">
      {/* ── Top bar ─────────────────────────────────────────────────── */}
      <header className="border-b border-bg-border px-6 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <svg width="24" height="24" viewBox="0 0 32 32" className="shrink-0">
            <polygon points="16,3 29,10 29,22 16,29 3,22 3,10"
              fill="none" stroke="#00d4ff" strokeWidth="2"/>
            <circle cx="16" cy="16" r="4" fill="#00d4ff"/>
          </svg>
          <span className="text-accent font-display font-medium tracking-widest text-sm glow-text">
            SENTINAI
          </span>
          <span className="text-muted text-xs tracking-wider">// SECURITY OPERATIONS</span>
        </div>

        <div className="flex items-center gap-6 text-xs">
          <div className="flex items-center gap-2">
            <span className={clsx("font-medium", statusColor)}>
              ● {ready?.status?.toUpperCase() ?? (isBackendUp ? "CONNECTING…" : "OFFLINE")}
            </span>
            <span className="text-muted">{live?.service ?? "sentinai"}</span>
          </div>

          {ready?.checks && (
            <div className="hidden md:flex items-center gap-1">
              {ready.checks.map((c) => (
                <div
                  key={c.name}
                  title={`${c.name}: ${c.status}${c.detail ? " — " + c.detail : ""}`}
                  className={clsx(
                    "w-1.5 h-4 rounded-sm",
                    c.status === "ok"       ? "bg-ok"      :
                    c.status === "degraded" ? "bg-warn"    : "bg-red-500"
                  )}
                />
              ))}
            </div>
          )}

          <button
            onClick={handleLogout}
            className="text-muted hover:text-text transition-colors tracking-wider"
          >
            [LOGOUT]
          </button>
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        {/* ── Sidebar ─────────────────────────────────────────────────── */}
        <nav className="w-44 border-r border-bg-border shrink-0 py-6 flex flex-col gap-1 px-3">
          {NAV.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                clsx(
                  "flex items-center gap-2 px-3 py-2 text-xs tracking-widest",
                  "transition-all rounded-sm border-l-2",
                  isActive
                    ? "text-accent bg-accent/5 border-accent glow-text"
                    : "text-muted hover:text-text hover:bg-bg-card border-transparent"
                )
              }
            >
              <span className="w-4 text-center">{icon}</span>
              {label}
            </NavLink>
          ))}

          <div className="mt-auto pt-6 px-3 text-xs text-muted border-t border-bg-border">
            <div className="mb-1 tracking-wider">CHECKS</div>
            {ready?.checks?.map((c) => (
              <div key={c.name} className="flex justify-between py-0.5">
                <span className="truncate">{c.name}</span>
                <span className={
                  c.status === "ok"       ? "text-ok"   :
                  c.status === "degraded" ? "text-warn"  : "text-red-500"
                }>
                  {c.status === "ok" ? "OK" : c.status === "degraded" ? "DEG" : "FAIL"}
                </span>
              </div>
            ))}
          </div>
        </nav>

        {/* ── Main ───────────────────────────────────────────────────── */}
        <main className="flex-1 overflow-auto p-6 animate-fade-in">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
