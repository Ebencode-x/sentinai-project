import { useEffect } from "react";
import { Outlet, NavLink, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  AlertTriangle,
  ClipboardList,
  ShieldCheck,
  GitCompareArrows,
  Settings,
  Sun,
  Moon,
  LogOut,
  Activity,
} from "lucide-react";
import { useApiKey }  from "@/hooks/useApiKey";
import { useHealth }  from "@/hooks/useHealth";
import { useToast }   from "@/components/Toast";
import { useTheme }   from "@/hooks/useTheme";
import clsx from "clsx";

const NAV = [
  { to: "/dashboard", label: "Overview",  Icon: LayoutDashboard },
  { to: "/incidents", label: "Incidents", Icon: AlertTriangle    },
  { to: "/audit",     label: "Audit",     Icon: ClipboardList    },
  { to: "/policy",    label: "Policy",    Icon: ShieldCheck      },
  { to: "/diff",      label: "Diff",      Icon: GitCompareArrows          },
  { to: "/settings",  label: "Settings",  Icon: Settings         },
];

export default function Layout() {
  const { clearKey }             = useApiKey();
  const navigate                 = useNavigate();
  const { live, ready, isBackendUp } = useHealth();
  const { toast }                = useToast();
  const { theme, toggle }        = useTheme();

  useEffect(() => {
    if (isBackendUp === false) {
      toast("Backend unreachable — check VITE_API_URL", "error");
    }
  }, [isBackendUp, toast]);

  const statusOk      = ready?.status === "ok";
  const statusDeg     = ready?.status === "degraded";
  const statusOffline = isBackendUp === false;

  function handleLogout() {
    clearKey();
    navigate("/");
  }

  return (
    <div
      className="flex h-screen overflow-hidden"
      style={{ background: "var(--bg-base)", color: "var(--text-primary)" }}
    >
      {/* ── Sidebar ──────────────────────────────────────────────── */}
      <aside
        className="flex flex-col items-center w-14 shrink-0 py-4 gap-1"
        style={{
          background:  "var(--bg-surface)",
          borderRight: "0.5px solid var(--border)",
        }}
      >
        {/* Logo */}
        <div className="mb-3 flex items-center justify-center">
          <div
            className="w-8 h-8 rounded-md flex items-center justify-center"
            style={{ background: "var(--cyan)" }}
          >
            <svg viewBox="0 0 18 18" width="16" height="16" fill="none">
              <path
                d="M9 1L16 5V13L9 17L2 13V5L9 1Z"
                stroke="var(--bg-base)"
                strokeWidth="1.5"
              />
              <circle cx="9" cy="9" r="2.5" fill="var(--bg-base)" />
            </svg>
          </div>
        </div>

        {/* Nav items */}
        {NAV.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            title={label}
            className={({ isActive }) =>
              clsx(
                "w-9 h-9 rounded-md flex items-center justify-center transition-all group relative",
                isActive
                  ? "text-[var(--cyan)]"
                  : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
              )
            }
            style={({ isActive }) =>
              isActive
                ? { background: "var(--cyan-dim)" }
                : undefined
            }
          >
            {({ isActive }) => (
              <>
                <Icon size={16} strokeWidth={isActive ? 2 : 1.75} />
                {/* Tooltip */}
                <span
                  className="pointer-events-none absolute left-full ml-2 px-2 py-1 text-xs rounded-md
                             opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-50
                             font-body"
                  style={{
                    background: "var(--bg-panel)",
                    color:      "var(--text-primary)",
                    border:     "0.5px solid var(--border-strong)",
                    fontFamily: "'DM Sans', sans-serif",
                    fontSize:   "11px",
                  }}
                >
                  {label}
                </span>
              </>
            )}
          </NavLink>
        ))}

        {/* Bottom controls */}
        <div className="mt-auto flex flex-col items-center gap-2">
          {/* Status dot */}
          <div
            title={ready?.status ?? (isBackendUp ? "connecting" : "offline")}
            className={clsx(
              "w-2 h-2 rounded-full",
              statusOk      ? "animate-pulse-dot" : "",
            )}
            style={{
              background: statusOk
                ? "var(--green)"
                : statusDeg
                ? "var(--amber)"
                : "var(--red)",
            }}
          />

          {/* Theme toggle */}
          <button
            onClick={toggle}
            title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
            className="w-9 h-9 rounded-md flex items-center justify-center transition-all
                       text-[var(--text-muted)] hover:text-[var(--text-secondary)]
                       hover:bg-[var(--bg-elevated)]"
          >
            {theme === "dark"
              ? <Sun  size={15} strokeWidth={1.75} />
              : <Moon size={15} strokeWidth={1.75} />
            }
          </button>

          {/* Logout */}
          <button
            onClick={handleLogout}
            title="Logout"
            className="w-9 h-9 rounded-md flex items-center justify-center transition-all
                       text-[var(--text-muted)] hover:text-[var(--red)]
                       hover:bg-[var(--red-dim)]"
          >
            <LogOut size={15} strokeWidth={1.75} />
          </button>

          {/* Avatar */}
          <div
            className="w-7 h-7 rounded-full flex items-center justify-center mt-1
                       font-mono text-[10px] font-medium text-white"
            style={{
              background: "linear-gradient(135deg, var(--purple), var(--cyan))",
            }}
          >
            EB
          </div>
        </div>
      </aside>

      {/* ── Main area ────────────────────────────────────────────── */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        {/* Topbar */}
        <header
          className="h-12 shrink-0 flex items-center px-5 gap-3"
          style={{
            background:   "var(--bg-surface)",
            borderBottom: "0.5px solid var(--border)",
          }}
        >
          {/* Breadcrumb / page title rendered by each page via a portal in future;
              for now show service name */}
          <span
            className="font-display font-semibold tracking-tight text-sm"
            style={{ color: "var(--text-primary)", fontFamily: "'Syne', sans-serif" }}
          >
            SentinAI
          </span>
          <span
            className="text-xs font-mono"
            style={{ color: "var(--text-muted)", fontFamily: "'IBM Plex Mono', monospace" }}
          >
            / {live?.service ?? "production"}
          </span>

          <div className="ml-auto flex items-center gap-3">
            {/* Backend health checks pill row */}
            {ready?.checks && (
              <div className="hidden md:flex items-center gap-1">
                {ready.checks.map((c) => (
                  <div
                    key={c.name}
                    title={`${c.name}: ${c.status}${c.detail ? " — " + c.detail : ""}`}
                    className="w-1.5 h-4 rounded-sm"
                    style={{
                      background:
                        c.status === "ok"
                          ? "var(--green)"
                          : c.status === "degraded"
                          ? "var(--amber)"
                          : "var(--red)",
                    }}
                  />
                ))}
              </div>
            )}

            {/* Live / Offline badge */}
            <div
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-mono font-medium tracking-widest"
              style={
                statusOffline
                  ? { background: "var(--red-dim)",  color: "var(--red)",   border: "0.5px solid var(--red)"   }
                  : statusDeg
                  ? { background: "var(--amber-dim)", color: "var(--amber)", border: "0.5px solid var(--amber)" }
                  : { background: "var(--red-dim)",   color: "var(--red)",   border: "0.5px solid var(--red)"   }
              }
            >
              <span
                className="w-1.5 h-1.5 rounded-full animate-pulse-dot"
                style={{
                  background: statusOffline ? "var(--red)" : statusDeg ? "var(--amber)" : "var(--red)",
                }}
              />
              {statusOffline ? "OFFLINE" : statusDeg ? "DEGRADED" : "LIVE"}
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-5 animate-fade-in">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
