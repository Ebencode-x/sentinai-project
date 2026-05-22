import { useEffect } from "react";
import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { LayoutDashboard, AlertTriangle, ClipboardList, ShieldCheck, GitCompareArrows, Settings, Sun, Moon, LogOut } from "lucide-react";
import { useApiKey } from "@/hooks/useApiKey";
import { useHealth } from "@/hooks/useHealth";
import { useToast } from "@/components/Toast";
import { useTheme } from "@/hooks/useTheme";
import clsx from "clsx";
import ChatPanel from "@/components/ChatPanel";

const NAV = [
  { to: "/dashboard", label: "Overview",  Icon: LayoutDashboard },
  { to: "/incidents", label: "Incidents", Icon: AlertTriangle },
  { to: "/audit",     label: "Audit",     Icon: ClipboardList },
  { to: "/policy",    label: "Policy",    Icon: ShieldCheck },
  { to: "/diff",      label: "Diff",      Icon: GitCompareArrows },
  { to: "/settings",  label: "Settings",  Icon: Settings },
];

export default function Layout() {
  const { clearKey } = useApiKey();
  const navigate = useNavigate();
  const { live, ready, isBackendUp } = useHealth();
  const { toast } = useToast();
  const { theme, toggle } = useTheme();

  useEffect(() => {
    if (isBackendUp === false) toast("Backend unreachable — check VITE_API_URL", "error");
  }, [isBackendUp, toast]);

  const statusOk = ready?.status === "ok";
  const statusDeg = ready?.status === "degraded";
  const statusOffline = isBackendUp === false;

  const badge = statusOffline
    ? { bg: "var(--red-dim)",   color: "var(--red)",   dot: "var(--red)",   label: "OFFLINE" }
    : statusDeg
    ? { bg: "var(--amber-dim)", color: "var(--amber)", dot: "var(--amber)", label: "DEGRADED" }
    : statusOk
    ? { bg: "var(--green-dim)", color: "var(--green)", dot: "var(--green)", label: "LIVE" }
    : { bg: "var(--bg-panel)",  color: "var(--text-muted)", dot: "var(--text-muted)", label: "CONNECTING" };

  function handleLogout() { clearKey(); navigate("/"); }

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "var(--bg-base)", color: "var(--text-primary)" }}>
      <aside className="flex flex-col items-center w-14 shrink-0 py-4 gap-1" style={{ background: "var(--bg-surface)", borderRight: "0.5px solid var(--border)" }}>
        <div className="mb-3 flex items-center justify-center">
          <div className="w-8 h-8 rounded-md flex items-center justify-center" style={{ background: "var(--cyan)" }}>
            <svg viewBox="0 0 18 18" width="16" height="16" fill="none">
              <path d="M9 1L16 5V13L9 17L2 13V5L9 1Z" stroke="var(--bg-base)" strokeWidth="1.5" />
              <circle cx="9" cy="9" r="2.5" fill="var(--bg-base)" />
            </svg>
          </div>
        </div>

        {NAV.map(({ to, label, Icon }) => (
          <NavLink key={to} to={to} title={label}
            className={({ isActive }) => clsx("w-9 h-9 rounded-md flex items-center justify-center transition-all group relative",
              isActive ? "text-[var(--cyan)]" : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]")}
            style={({ isActive }) => isActive ? { background: "var(--cyan-dim)" } : undefined}>
            {({ isActive }) => (
              <>
                <Icon size={16} strokeWidth={isActive ? 2 : 1.75} />
                <span className="pointer-events-none absolute left-full ml-2 px-2 py-1 text-xs rounded-md opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-50"
                  style={{ background: "var(--bg-panel)", color: "var(--text-primary)", border: "0.5px solid var(--border-strong)", fontFamily: "DM Sans, sans-serif", fontSize: "11px" }}>
                  {label}
                </span>
              </>
            )}
          </NavLink>
        ))}

        <div className="mt-auto flex flex-col items-center gap-2">
          <div title={ready?.status ?? (isBackendUp === null ? "connecting" : "offline")}
            className={clsx("w-2 h-2 rounded-full", statusOk ? "animate-pulse-dot" : "")}
            style={{ background: badge.dot }} />
          <button onClick={toggle} title={theme === "dark" ? "Light mode" : "Dark mode"}
            className="w-9 h-9 rounded-md flex items-center justify-center transition-all text-[var(--text-muted)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]">
            {theme === "dark" ? <Sun size={15} strokeWidth={1.75} /> : <Moon size={15} strokeWidth={1.75} />}
          </button>
          <button onClick={handleLogout} title="Sign out"
            className="w-9 h-9 rounded-md flex items-center justify-center transition-all text-[var(--text-muted)] hover:text-[var(--red)] hover:bg-[var(--red-dim)]">
            <LogOut size={15} strokeWidth={1.75} />
          </button>
          <div className="w-7 h-7 rounded-full flex items-center justify-center mt-1 text-[10px] font-medium"
            style={{ background: "linear-gradient(135deg, var(--purple), var(--cyan))", color: "var(--bg-base)", fontFamily: "DM Sans, sans-serif" }}>EB</div>
        </div>
      </aside>

      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <header className="h-12 shrink-0 flex items-center px-5 gap-3" style={{ background: "var(--bg-surface)", borderBottom: "0.5px solid var(--border)" }}>
          <span className="font-display font-semibold tracking-tight text-sm" style={{ color: "var(--text-primary)", fontFamily: "Syne, sans-serif" }}>SentinAI</span>
          <span className="text-xs" style={{ color: "var(--text-muted)", fontFamily: "IBM Plex Mono, monospace" }}>/ {live?.service ?? "production"}</span>
          <div className="ml-auto flex items-center gap-3">
            {ready?.checks && (
              <div className="hidden md:flex items-center gap-1">
                {ready.checks.map((c) => (
                  <div key={c.name} title={c.name + ": " + c.status}
                    className="w-1.5 h-4 rounded-sm"
                    style={{ background: c.status === "ok" ? "var(--green)" : c.status === "degraded" ? "var(--amber)" : "var(--red)" }} />
                ))}
              </div>
            )}
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-mono font-medium tracking-widest"
              style={{ background: badge.bg, color: badge.color, border: "0.5px solid " + badge.color, fontFamily: "IBM Plex Mono, monospace" }}>
              <span className={clsx("w-1.5 h-1.5 rounded-full", statusOk ? "animate-pulse-dot" : "")} style={{ background: badge.dot }} />
              {badge.label}
            </div>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-5 animate-fade-in"><Outlet /></main>
      </div>
      <ChatPanel />
    </div>
  );
}
