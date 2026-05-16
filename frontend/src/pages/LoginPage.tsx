import { useState, FormEvent } from "react";
import { useApiKey } from "@/hooks/useApiKey";

export default function LoginPage() {
  const { setKey } = useApiKey();
  const [value, setValue] = useState("");
  const [error, setError] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!value.trim()) {
      setError("API key required");
      return;
    }
    setKey(value.trim());
  }

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="flex items-center gap-3 mb-12 justify-center">
          <svg width="32" height="32" viewBox="0 0 32 32">
            <polygon points="16,3 29,10 29,22 16,29 3,22 3,10"
              fill="none" stroke="#00d4ff" strokeWidth="2"/>
            <circle cx="16" cy="16" r="4" fill="#00d4ff"/>
          </svg>
          <span className="text-accent text-xl font-display tracking-widest glow-text">
            SENTINAI
          </span>
        </div>

        <div className="border border-bg-border bg-bg-card p-8 rounded-sm">
          <div className="text-xs text-muted tracking-widest mb-6">
            // AUTHENTICATE — SECURITY OPERATIONS CONSOLE
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div>
              <label className="block text-xs text-muted tracking-wider mb-2">
                API KEY
              </label>
              <input
                type="password"
                value={value}
                onChange={(e) => { setValue(e.target.value); setError(""); }}
                placeholder="sk-sentinai-••••••••"
                className="w-full bg-bg border border-bg-border text-text text-sm px-4 py-3
                           font-mono rounded-sm outline-none
                           focus:border-accent focus:shadow-glow-accent transition-all
                           placeholder:text-muted/40"
                autoFocus
              />
              {error && (
                <p className="text-warn text-xs mt-2 tracking-wide">{error}</p>
              )}
            </div>

            <button
              type="submit"
              className="mt-2 w-full bg-accent/10 border border-accent text-accent
                         text-xs tracking-widest py-3 rounded-sm
                         hover:bg-accent hover:text-bg transition-all duration-200
                         hover:shadow-glow-accent"
            >
              AUTHENTICATE →
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-muted mt-6 tracking-wider">
          SET YOUR KEY VIA <span className="text-accent">SENTINAI_API_KEY</span> ENV VAR
        </p>
      </div>
    </div>
  );
}
