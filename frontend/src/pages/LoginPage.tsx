import { FormEvent, useState } from "react";
import { Eye, EyeOff, Moon, Sun } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useTheme } from "@/hooks/useTheme";
import { http } from "@/api/client";

// Read by the response interceptor in api/client.ts. A failed login must show
// its own error message instead of clearing the session and reloading the page.
const NO_AUTH_REDIRECT = { skipAuthRedirect: true } as object;

const INPUT =
  "w-full rounded-md px-3 h-10 text-sm outline-none transition-colors " +
  "bg-[var(--bg-panel)] border border-[var(--border-strong)] focus:border-[var(--brand)] " +
  "text-[var(--text-primary)] placeholder:text-[var(--text-muted)]";

export default function LoginPage() {
  const { login } = useAuth();
  const { theme, toggle } = useTheme();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [visible, setVisible] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmedEmail = email.trim();
    if (!trimmedEmail || !password) {
      setError("Email and password are required");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await http.post(
        "/api/auth/login",
        { email: trimmedEmail, password },
        NO_AUTH_REDIRECT
      );
      login(res.data.token, { email: res.data.email, role: res.data.role }, res.data.expires_at);
    } catch (err) {
      const response = (err as { response?: { status?: number } })?.response;
      if (!response) setError("Cannot reach the server. Check your connection and try again.");
      else if (response.status === 401) setError("Invalid email or password");
      else setError("Login failed. Try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ background: "var(--bg-base)", color: "var(--text-primary)" }}>
      <header className="flex items-center justify-end px-6 py-4">
        <button
          onClick={toggle}
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          className="w-8 h-8 rounded-md flex items-center justify-center transition-colors text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
        >
          {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
        </button>
      </header>

      <main className="flex-1 flex items-center justify-center px-4 pb-16">
        <div
          className="w-full max-w-[380px] rounded-lg p-6 flex flex-col gap-6"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
        >
          <div className="flex flex-col items-center gap-3 text-center">
            <img src="/apple-touch-icon.png" alt="SentinAI" className="w-10 h-10 rounded-lg" />
            <div>
              <h1 className="text-xl font-semibold tracking-tight">Sign in to SentinAI</h1>
              <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
                Self-healing DevOps agent
              </p>
            </div>
          </div>

          <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="email" className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                Email
              </label>
              <input
                id="email"
                name="email"
                type="email"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  setError("");
                }}
                placeholder="you@company.com"
                autoFocus
                autoComplete="username"
                spellCheck={false}
                className={INPUT}
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="password" className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  name="password"
                  type={visible ? "text" : "password"}
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    setError("");
                  }}
                  placeholder="Your password"
                  autoComplete="current-password"
                  spellCheck={false}
                  className={`${INPUT} pr-10`}
                />
                <button
                  type="button"
                  tabIndex={-1}
                  onClick={() => setVisible((v) => !v)}
                  aria-label={visible ? "Hide password" : "Show password"}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
                >
                  {visible ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {error && (
              <p
                role="alert"
                className="rounded-md px-3 py-2 text-sm"
                style={{ background: "var(--red-dim)", color: "var(--red)" }}
              >
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-md h-10 text-sm font-medium transition-opacity disabled:opacity-70"
              style={{ background: "var(--brand)", color: "#1a1a1a", cursor: loading ? "wait" : "pointer" }}
            >
              {loading ? "Signing in" : "Sign in"}
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}
