import { useEffect } from "react";
import { Outlet, NavLink, useNavigate } from "react-router";
import { LogOut } from "lucide-react";
import ThemeIcon from "@/components/ThemeIcon";
import { useAuth } from "@/hooks/useAuth";
import { useHealth } from "@/hooks/useHealth";
import { useToast } from "@/components/Toast";
import { useTheme } from "@/hooks/useTheme";
import clsx from "clsx";
import ChatPanel from "@/components/ChatPanel";

const NAV = [
  { to: "/dashboard", label: "Overview" },
  { to: "/incidents", label: "Incidents" },
  { to: "/audit", label: "Audit" },
  { to: "/policy", label: "Policy" },
  { to: "/diff", label: "Diff" },
  { to: "/settings", label: "Settings" },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { isBackendUp } = useHealth();
  const { toast } = useToast();
  const { theme, toggle } = useTheme();

  useEffect(() => {
    if (isBackendUp === false) toast("Backend unreachable, check VITE_API_URL", "error");
  }, [isBackendUp, toast]);

  function handleLogout() {
    logout();
    navigate("/login");
  }

  const initials = (user?.email ?? "?").slice(0, 2).toUpperCase();

  return (
    <div className="flex flex-col h-screen overflow-hidden" style={{ background: "var(--bg-base)", color: "var(--text-primary)" }}>
      <header
        className="shrink-0 h-14 sticky top-0 z-30"
        style={{ background: "var(--bg-surface)", borderBottom: "1px solid var(--border)" }}
      >
        <div className="h-full max-w-[1200px] mx-auto px-4 flex items-center gap-6">
          <div className="flex items-center gap-2 shrink-0">
            <img src="/apple-touch-icon.png" alt="SentinAI" className="w-7 h-7 rounded-md" />
            <span className="text-[15px] font-semibold tracking-tight">SentinAI</span>
          </div>

          <nav className="flex items-center gap-1 overflow-x-auto min-w-0">
            {NAV.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  clsx(
                    "px-3 py-1.5 rounded-md text-sm font-medium whitespace-nowrap transition-colors",
                    isActive
                      ? "bg-[var(--bg-hover)] text-[var(--text-primary)]"
                      : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-panel)]"
                  )
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-1 shrink-0">
            <button
              onClick={toggle}
              title={theme === "dark" ? "Light mode" : "Dark mode"}
              className="w-8 h-8 rounded-md flex items-center justify-center transition-colors text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
            >
              <ThemeIcon dark={theme === "dark"} />
            </button>
            <span className="hidden md:block text-xs px-2" style={{ color: "var(--text-muted)" }}>
              {user?.email}
            </span>
            <div
              title={user?.email}
              className="w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-semibold"
              style={{ background: "var(--bg-panel)", color: "var(--text-secondary)", border: "1px solid var(--border-strong)" }}
            >
              {initials}
            </div>
            <button
              onClick={handleLogout}
              title="Sign out"
              className="w-8 h-8 rounded-md flex items-center justify-center transition-colors text-[var(--text-secondary)] hover:text-[var(--red)] hover:bg-[var(--red-dim)]"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-[1200px] mx-auto px-4 py-6 animate-fade-in">
          <Outlet />
        </div>
      </main>
      <ChatPanel />
    </div>
  );
}
