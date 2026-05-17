import { useState, KeyboardEvent } from "react";
import { useApiKey } from "@/hooks/useApiKey";
import { Shield, ArrowRight, Eye, EyeOff } from "lucide-react";

export default function LoginPage() {
  const { setKey }           = useApiKey();
  const [value, setValue]    = useState("");
  const [error, setError]    = useState("");
  const [visible, setVisible] = useState(false);
  const [loading, setLoading] = useState(false);

  function handleSubmit() {
    if (!value.trim()) {
      setError("API key is required");
      return;
    }
    setLoading(true);
    setTimeout(() => {
      setKey(value.trim());
      setLoading(false);
    }, 600);
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") handleSubmit();
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center p-4"
      style={{ background: "var(--bg-base)" }}
    >
      {/* Background grid */}
      <div
        className="fixed inset-0 pointer-events-none"
        style={{
          backgroundImage: `
            linear-gradient(var(--border) 1px, transparent 1px),
            linear-gradient(90deg, var(--border) 1px, transparent 1px)
          `,
          backgroundSize: "48px 48px",
          maskImage: "radial-gradient(ellipse 80% 80% at 50% 50%, black 40%, transparent 100%)",
          WebkitMaskImage: "radial-gradient(ellipse 80% 80% at 50% 50%, black 40%, transparent 100%)",
        }}
      />

      <div className="w-full max-w-sm relative z-10 animate-slide-up">

        {/* Logo mark */}
        <div className="flex flex-col items-center mb-10">
          <div
            className="w-12 h-12 rounded-xl flex items-center justify-center mb-4"
            style={{ background: "var(--cyan-dim)", border: "0.5px solid var(--cyan)" }}
          >
            <Shield size={22} style={{ color: "var(--cyan)" }} strokeWidth={1.5} />
          </div>
          <h1
            className="font-display font-bold text-2xl tracking-tight"
            style={{ color: "var(--text-primary)", fontFamily: "'Syne', sans-serif" }}
          >
            SentinAI
          </h1>
          <p
            className="text-xs font-mono mt-1 tracking-widest uppercase"
            style={{ color: "var(--text-muted)", fontFamily: "'IBM Plex Mono', monospace" }}
          >
            Security Operations
          </p>
        </div>

        {/* Card */}
        <div
          className="rounded-xl p-6 flex flex-col gap-5"
          style={{
            background: "var(--bg-surface)",
            border:     "0.5px solid var(--border-strong)",
          }}
        >
          <div>
            <p
              className="text-xs font-mono tracking-widest"
              style={{ color: "var(--text-muted)", fontFamily: "'IBM Plex Mono', monospace" }}
            >
              // Authenticate to continue
            </p>
          </div>

          {/* Input */}
          <div className="flex flex-col gap-1.5">
            <label
              className="text-[10px] font-mono tracking-widest uppercase"
              style={{ color: "var(--text-muted)", fontFamily: "'IBM Plex Mono', monospace" }}
            >
              API Key
            </label>
            <div className="relative">
              <input
                type={visible ? "text" : "password"}
                value={value}
                onChange={(e) => { setValue(e.target.value); setError(""); }}
                onKeyDown={handleKeyDown}
                placeholder="sk-sentinai-••••••••"
                autoFocus
                className="w-full rounded-md px-3 py-2.5 pr-10 text-sm font-mono outline-none transition-all"
                style={{
                  background:  "var(--bg-elevated)",
                  border:      error ? "0.5px solid var(--red)" : "0.5px solid var(--border-strong)",
                  color:       "var(--text-primary)",
                  fontFamily:  "'IBM Plex Mono', monospace",
                  fontSize:    "13px",
                }}
                onFocus={(e) => {
                  if (!error) e.currentTarget.style.border = "0.5px solid var(--cyan)";
                  e.currentTarget.style.boxShadow = error ? "0 0 0 3px var(--red-dim)" : "0 0 0 3px var(--cyan-dim)";
                }}
                onBlur={(e) => {
                  e.currentTarget.style.border = error ? "0.5px solid var(--red)" : "0.5px solid var(--border-strong)";
                  e.currentTarget.style.boxShadow = "none";
                }}
              />
              <button
                type="button"
                onClick={() => setVisible((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 transition-colors"
                style={{ color: "var(--text-muted)" }}
                onMouseEnter={(e) => (e.currentTarget.style.color = "var(--text-secondary)")}
                onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-muted)")}
              >
                {visible
                  ? <EyeOff size={14} strokeWidth={1.75} />
                  : <Eye    size={14} strokeWidth={1.75} />
                }
              </button>
            </div>
            {error && (
              <p
                className="text-[11px] font-mono"
                style={{ color: "var(--red)", fontFamily: "'IBM Plex Mono', monospace" }}
              >
                {error}
              </p>
            )}
          </div>

          {/* Submit */}
          <button
            type="button"
            onClick={handleSubmit}
            disabled={loading}
            className="w-full rounded-md py-2.5 flex items-center justify-center gap-2 text-sm font-medium transition-all"
            style={{
              background:  loading ? "var(--cyan-dim)" : "var(--cyan)",
              color:       loading ? "var(--cyan)"     : "var(--bg-base)",
              fontFamily:  "'DM Sans', sans-serif",
              border:      "none",
              cursor:      loading ? "wait" : "pointer",
              opacity:     loading ? 0.8 : 1,
            }}
            onMouseEnter={(e) => {
              if (!loading) e.currentTarget.style.opacity = "0.88";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.opacity = "1";
            }}
          >
            {loading ? (
              <>
                <span
                  className="w-3.5 h-3.5 rounded-full border-2 animate-spin"
                  style={{ borderColor: "var(--cyan)", borderTopColor: "transparent" }}
                />
                Authenticating
              </>
            ) : (
              <>
                Authenticate
                <ArrowRight size={15} strokeWidth={2} />
              </>
            )}
          </button>
        </div>

        {/* Footer hint */}
        <p
          className="text-center text-[10px] font-mono mt-5 tracking-wider"
          style={{ color: "var(--text-muted)", fontFamily: "'IBM Plex Mono', monospace" }}
        >
          Set via{" "}
          <span style={{ color: "var(--cyan)" }}>SENTINAI_API_KEY</span>
          {" "}env var
        </p>
      </div>
    </div>
  );
}
