import { useState, KeyboardEvent, useEffect } from "react";
import { useApiKey } from "@/hooks/useApiKey";
import { Shield, ArrowRight, Eye, EyeOff, Sun, Moon } from "lucide-react";
import { useTheme } from "@/hooks/useTheme";

export default function LoginPage() {
  const { setKey } = useApiKey();
  const { theme, toggle } = useTheme();
  const [value, setValue] = useState("");
  const [error, setError] = useState("");
  const [visible, setVisible] = useState(false);
  const [loading, setLoading] = useState(false);
  const [dots, setDots] = useState("");

  useEffect(() => {
    if (!loading) return;
    const id = setInterval(() => setDots((d) => (d.length >= 3 ? "" : d + ".")), 400);
    return () => clearInterval(id);
  }, [loading]);

  async function handleSubmit() {
    const trimmed = value.trim();
    if (!trimmed) { setError("API key required"); return; }
    if (!trimmed.startsWith("sk-")) { setError("Invalid key format — must begin with sk-"); return; }
    setLoading(true); setError("");
    await new Promise((r) => setTimeout(r, 800));
    setKey(trimmed); setLoading(false);
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") handleSubmit();
  }

  const bg = "var(--bg-base)";
  const fg = "var(--text-primary)";

  return (
    <div className="min-h-screen flex flex-col" style={{ background: bg, color: fg }}>
      <header className="flex items-center justify-between px-6 py-4">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: "var(--cyan)" }}>
            <Shield size={14} style={{ color: "var(--bg-base)" }} strokeWidth={2} />
          </div>
          <span className="font-display font-semibold text-sm" style={{ fontFamily: "Syne, sans-serif", color: fg }}>SentinAI</span>
        </div>
        <button onClick={toggle} className="w-8 h-8 rounded-md flex items-center justify-center" style={{ color: "var(--text-muted)" }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "var(--text-secondary)")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-muted)")}>
          {theme === "dark" ? <Sun size={15} strokeWidth={1.75} /> : <Moon size={15} strokeWidth={1.75} />}
        </button>
      </header>

      <div className="flex-1 flex items-center justify-center px-4">
        <div className="w-full max-w-[360px] flex flex-col gap-8">
          <div className="flex flex-col gap-2">
            <h1 className="font-display font-bold text-[28px] tracking-tight" style={{ fontFamily: "Syne, sans-serif" }}>Welcome back</h1>
            <p className="text-sm" style={{ fontFamily: "DM Sans, sans-serif", color: "var(--text-secondary)" }}>Enter your API key to access the operations console.</p>
          </div>

          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium" style={{ fontFamily: "DM Sans, sans-serif", color: "var(--text-secondary)" }}>API key</label>
              <div className="relative">
                <input type={visible ? "text" : "password"} value={value}
                  onChange={(e) => { setValue(e.target.value); setError(""); }}
                  onKeyDown={handleKeyDown} placeholder="sk-sentinai-••••••••"
                  autoFocus autoComplete="current-password" spellCheck={false}
                  className="w-full rounded-lg px-3.5 py-2.5 pr-10 text-sm outline-none transition-all"
                  style={{ background: "var(--bg-surface)", border: error ? "1px solid var(--red)" : "1px solid var(--border-strong)", color: fg, fontFamily: "IBM Plex Mono, monospace", fontSize: "13px" }}
                  onFocus={(e) => { e.currentTarget.style.border = error ? "1px solid var(--red)" : "1px solid var(--cyan)"; e.currentTarget.style.boxShadow = error ? "0 0 0 3px var(--red-dim)" : "0 0 0 3px var(--cyan-dim)"; }}
                  onBlur={(e) => { e.currentTarget.style.border = error ? "1px solid var(--red)" : "1px solid var(--border-strong)"; e.currentTarget.style.boxShadow = "none"; }} />
                <button type="button" tabIndex={-1} onClick={() => setVisible((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2" style={{ color: "var(--text-muted)" }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = "var(--text-secondary)")}
                  onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-muted)")}>
                  {visible ? <EyeOff size={14} strokeWidth={1.75} /> : <Eye size={14} strokeWidth={1.75} />}
                </button>
              </div>
              {error && <p className="text-xs" style={{ color: "var(--red)", fontFamily: "DM Sans, sans-serif" }}>{error}</p>}
            </div>

            <button type="button" onClick={handleSubmit} disabled={loading}
              className="w-full rounded-lg py-2.5 flex items-center justify-center gap-2 text-sm font-medium transition-all"
              style={{ background: "var(--cyan)", color: "var(--bg-base)", fontFamily: "DM Sans, sans-serif", fontWeight: 500, border: "none", cursor: loading ? "wait" : "pointer", opacity: loading ? 0.75 : 1 }}
              onMouseEnter={(e) => { if (!loading) e.currentTarget.style.opacity = "0.88"; }}
              onMouseLeave={(e) => { e.currentTarget.style.opacity = loading ? "0.75" : "1"; }}>
              {loading ? <span style={{ fontFamily: "IBM Plex Mono, monospace", fontSize: "13px" }}>Verifying{dots}</span>
                : <><span>Continue</span><ArrowRight size={15} strokeWidth={2} /></>}
            </button>
          </div>

          <p className="text-xs text-center" style={{ color: "var(--text-muted)", fontFamily: "DM Sans, sans-serif" }}>
            Key stored locally for 8 hours.{" "}
            <span style={{ color: "var(--text-secondary)" }}>Set <code style={{ fontFamily: "IBM Plex Mono, monospace", color: "var(--cyan)" }}>SENTINAI_API_KEY</code> on the server.</span>
          </p>
        </div>
      </div>

      <footer className="px-6 py-4 flex items-center justify-between">
        <span className="text-xs" style={{ color: "var(--text-muted)", fontFamily: "DM Sans, sans-serif" }}>SentinAI v0.1.0</span>
        <span className="text-xs" style={{ color: "var(--text-muted)", fontFamily: "DM Sans, sans-serif" }}>Self-healing DevOps agent</span>
      </footer>
    </div>
  );
}
