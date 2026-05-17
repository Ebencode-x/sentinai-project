import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["class"],
  theme: {
    extend: {
      fontFamily: {
        display: ["'Syne'", "sans-serif"],
        body:    ["'DM Sans'", "system-ui", "sans-serif"],
        mono:    ["'IBM Plex Mono'", "monospace"],
      },
      colors: {
        /* Map Tailwind classes → CSS variables so theme toggle is automatic */
        base:     "var(--bg-base)",
        surface:  "var(--bg-surface)",
        elevated: "var(--bg-elevated)",
        panel:    "var(--bg-panel)",
        hover:    "var(--bg-hover)",

        border:   "var(--border)",
        "border-strong": "var(--border-strong)",
        "border-focus":  "var(--border-focus)",

        primary:   "var(--text-primary)",
        secondary: "var(--text-secondary)",
        muted:     "var(--text-muted)",
        hint:      "var(--text-hint)",

        cyan:   "var(--cyan)",
        red:    "var(--red)",
        amber:  "var(--amber)",
        green:  "var(--green)",
        purple: "var(--purple)",

        /* Legacy aliases kept so existing pages don't break */
        bg: {
          DEFAULT: "var(--bg-base)",
          card:    "var(--bg-surface)",
          border:  "var(--border)",
        },
        accent: {
          DEFAULT: "var(--cyan)",
          dim:     "var(--cyan-dim)",
          glow:    "var(--cyan-glow)",
        },
        warn:  { DEFAULT: "var(--amber)", dim: "var(--amber-dim)" },
        ok:    { DEFAULT: "var(--green)",  dim: "var(--green-dim)" },
        text:  { DEFAULT: "var(--text-primary)", dim: "var(--text-secondary)" },
      },
      borderColor: {
        DEFAULT: "var(--border)",
      },
      boxShadow: {
        "glow-accent": "0 0 0 1px var(--cyan),  0 0 24px var(--cyan-glow)",
        "glow-red":    "0 0 0 1px var(--red),   0 0 24px var(--red-dim)",
        "glow-green":  "0 0 0 1px var(--green), 0 0 24px var(--green-dim)",
        "panel":       "0 1px 3px rgba(0,0,0,0.35)",
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4,0,0.6,1) infinite",
        "fade-in":    "fadeIn 0.25s ease-out both",
        "slide-up":   "slideUp 0.3s ease-out both",
        "pulse-dot":  "pulseDot 1.4s ease-in-out infinite",
      },
      keyframes: {
        fadeIn:   { from: { opacity: "0" },                               to: { opacity: "1" } },
        slideUp:  { from: { opacity: "0", transform: "translateY(10px)" }, to: { opacity: "1", transform: "translateY(0)" } },
        pulseDot: { "0%, 100%": { opacity: "1" }, "50%": { opacity: "0.25" } },
      },
      borderRadius: {
        sm:  "6px",
        md:  "8px",
        lg:  "12px",
        xl:  "16px",
        "2xl": "20px",
      },
    },
  },
  plugins: [],
} satisfies Config;
