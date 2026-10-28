import type { CSSProperties } from "react";
import { Link } from "react-router";
import { Sun, Moon } from "lucide-react";
import { useTheme } from "@/hooks/useTheme";
import { useMotionProfile } from "@/hooks/useMotion";
import Reveal from "@/components/Reveal";
import "./landing.css";

const SHOT = new URL("../assets/dashboard.png", import.meta.url).href;
const MUTED = "var(--text-muted)";

const LINES: { k?: string; t: string; c?: string }[] = [
  { t: "$ tail -f app.log", c: MUTED },
  { k: "09:14:02", t: "INFO  GET /orders 200" },
  { k: "09:14:07", t: "ERROR  [orders-api] KeyError: 'customer_id'", c: "var(--red)" },
  { k: "", t: "File \"orders/service.py\", line 88, in create_order", c: MUTED },
  { t: "\u00a0" },
  { k: "incident", t: "Critical, KeyError: 'customer_id'", c: "var(--brand)" },
  { k: "fix", t: "Read the field with .get(), return 422 when missing" },
  { k: "status", t: "Waiting for review", c: "var(--green)" },
];

const STEPS = [
  { n: "01", name: "Ingest", text: "Send ERROR lines from any service with a single HTTP request." },
  { n: "02", name: "Detect", text: "Tracebacks stay whole and repeats merge into one incident." },
  { n: "03", name: "Suggest", text: "A fix is drafted for every incident and checked before you see it." },
  { n: "04", name: "Audit", text: "Each suggestion is recorded with its model and waits for your review." },
];

const SNIPPET = [
  "curl -X POST https://sentinai.onrender.com/api/ingest \\",
  "  -H \"X-Ingest-Key: $SENTINAI_INGEST_KEY\" \\",
  "  -H \"Content-Type: application/json\" \\",
  "  -d '{\"source\": \"orders-api\", \"events\": [{\"message\": \"KeyError: customer_id\"}]}'",
];

const GUARDS = [
  { name: "Personal data masking", text: "Emails, phone numbers, IP addresses, OTPs and credentials are masked before a line is ever written." },
  { name: "Tamper-proof ingest", text: "The server writes every log line itself, so a client can never forge one." },
  { name: "Prompt injection defense", text: "Instructions hidden inside logs are treated as data, never as commands." },
  { name: "Patch validator", text: "Suggested code is parsed and checked structurally before it is shown." },
  { name: "Audit trail", text: "Every decision is stored with its time, provider and model, and can be reviewed." },
];

function Terminal() {
  return (
    <div className="ln-term">
      <div className="ln-term-bar">
        <span>app.log</span>
        <span>Sample output</span>
      </div>
      <div className="ln-code ln-sans">
        {LINES.map((l, i) => (
          <div key={i} className="ln-line" style={{ "--i": i } as CSSProperties}>
            {l.k !== undefined && <span className="ln-k">{l.k}</span>}
            <span style={{ color: l.c }}>{l.t}</span>
          </div>
        ))}
        <span className="ln-cursor" />
      </div>
    </div>
  );
}

export default function Landing() {
  const m = useMotionProfile();
  const { theme, toggle } = useTheme();
  const wrap = "max-w-[1120px] mx-auto px-5 md:px-8";

  return (
    <div data-motion={m} style={{ background: "var(--bg-base)", color: "var(--text-primary)" }} className="min-h-screen">
      <header className="sticky top-0 z-30 h-14" style={{ background: "var(--bg-surface)", borderBottom: "1px solid var(--border)" }}>
        <div className={`${wrap} h-full flex items-center gap-8`}>
          <Link to="/" className="flex items-center gap-2 shrink-0">
            <img src="/apple-touch-icon.png" alt="" className="w-7 h-7 rounded-md" />
            <span className="text-[15px] font-semibold tracking-tight">SentinAI</span>
          </Link>
          <nav className="hidden sm:flex items-center gap-6 text-sm" style={{ color: "var(--text-secondary)" }}>
            <a href="#how" className="ln-navlink transition-colors">How it works</a>
            <a href="#integrate" className="ln-navlink transition-colors">Integrate</a>
            <a href="#security" className="ln-navlink transition-colors">Security</a>
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={toggle}
              aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
              className="w-8 h-8 rounded-md flex items-center justify-center text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
            >
              {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            </button>
            <Link to="/login" className="ln-btn ln-primary rounded-md px-4 py-1.5 text-sm font-semibold">Sign in</Link>
          </div>
        </div>
      </header>

      <main>
        <section className={`${wrap} pt-14 md:pt-24 pb-12 md:pb-16 grid md:grid-cols-[1.05fr_1fr] gap-10 md:gap-14 items-center`}>
          <Reveal>
            <h1 className="text-[40px] md:text-[58px] leading-[1.05] font-semibold tracking-tight">
              Your logs already know <span style={{ color: "var(--brand)" }}>what broke.</span>
            </h1>
            <p className="mt-5 text-base md:text-lg max-w-[520px]" style={{ color: "var(--text-secondary)" }}>
              SentinAI reads your application logs, groups errors into incidents, drafts a fix for each one,
              and keeps an audit trail of every decision.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/login" className="ln-btn ln-primary rounded-md px-5 py-2.5 text-sm font-semibold">Sign in</Link>
              <a href="#how" className="ln-btn ln-ghost rounded-md px-5 py-2.5 text-sm font-semibold">How it works</a>
            </div>
          </Reveal>
          <Reveal delay={120}>
            <Terminal />
          </Reveal>
        </section>

        <section className={`${wrap} hidden md:block pb-24`}>
          <Reveal>
            <div className="ln-shot">
              <img src={SHOT} alt="SentinAI dashboard" loading="lazy" className="w-full h-auto block" />
            </div>
          </Reveal>
        </section>

        <section id="how" className="ln-anchor" style={{ borderTop: "1px solid var(--border)" }}>
          <div className={`${wrap} py-16 md:py-24`}>
            <Reveal>
              <h2 className="text-2xl md:text-4xl font-semibold tracking-tight">From a stack trace to a reviewed fix</h2>
              <p className="mt-3 max-w-[560px]" style={{ color: "var(--text-secondary)" }}>
                Four steps, and nothing is applied without you.
              </p>
            </Reveal>
            <div className="ln-track mt-12" />
            <div className="mt-8 md:mt-8 grid gap-8 md:grid-cols-4 md:gap-10">
              {STEPS.map((s, i) => (
                <Reveal key={s.n} delay={i * 80}>
                  <div className="ln-num text-sm font-semibold" style={{ color: "var(--brand)" }}>{s.n}</div>
                  <h3 className="mt-2 text-lg font-semibold">{s.name}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>{s.text}</p>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        <section id="integrate" className="ln-anchor" style={{ borderTop: "1px solid var(--border)" }}>
          <div className={`${wrap} py-16 md:py-24 grid md:grid-cols-[1fr_1.2fr] gap-10 md:gap-14 items-center`}>
            <Reveal>
              <h2 className="text-2xl md:text-4xl font-semibold tracking-tight">One request to connect a service</h2>
              <p className="mt-3 max-w-[460px]" style={{ color: "var(--text-secondary)" }}>
                Call the ingest endpoint directly or add a small log handler to your app. Errors reach the
                dashboard within seconds.
              </p>
            </Reveal>
            <Reveal delay={100}>
              <div className="ln-term">
                <div className="ln-term-bar"><span>terminal</span></div>
                <div className="ln-code">{SNIPPET.join("\n")}</div>
              </div>
            </Reveal>
          </div>
        </section>

        <section id="security" className="ln-anchor" style={{ borderTop: "1px solid var(--border)" }}>
          <div className={`${wrap} py-16 md:py-24 grid md:grid-cols-[1fr_1.4fr] gap-10 md:gap-14`}>
            <Reveal>
              <h2 className="text-2xl md:text-4xl font-semibold tracking-tight">Built to be trusted with your logs</h2>
              <p className="mt-3 max-w-[420px]" style={{ color: "var(--text-secondary)" }}>
                Logs hold secrets and untrusted text. SentinAI treats them that way.
              </p>
            </Reveal>
            <div>
              {GUARDS.map((g, i) => (
                <Reveal key={g.name} delay={i * 60}>
                  <div className="py-5 grid sm:grid-cols-[200px_1fr] gap-1 sm:gap-6" style={{ borderTop: i === 0 ? "none" : "1px solid var(--border)" }}>
                    <div className="font-semibold">{g.name}</div>
                    <div className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>{g.text}</div>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        <section style={{ borderTop: "1px solid var(--border)" }}>
          <div className={`${wrap} py-20 md:py-28 text-center`}>
            <Reveal>
              <h2 className="text-3xl md:text-5xl font-semibold tracking-tight">See it on your own errors.</h2>
              <div className="mt-8">
                <Link to="/login" className="ln-btn ln-primary rounded-md px-6 py-3 text-sm font-semibold inline-block">Sign in</Link>
              </div>
            </Reveal>
          </div>
        </section>
      </main>

      <footer style={{ borderTop: "1px solid var(--border)" }}>
        <div className={`${wrap} py-6 flex items-center justify-between text-xs`} style={{ color: "var(--text-muted)" }}>
          <span>SentinAI</span>
          <Link to="/login" className="ln-navlink transition-colors">Sign in</Link>
        </div>
      </footer>
    </div>
  );
}
