import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        mono: ["'JetBrains Mono'", "'Fira Code'", "monospace"],
        display: ["'DM Mono'", "monospace"],
      },
      colors: {
        bg:      { DEFAULT: "#080c10", card: "#0d1117", border: "#1a2332" },
        accent:  { DEFAULT: "#00d4ff", dim: "#0099bb", glow: "#00d4ff33" },
        warn:    { DEFAULT: "#ff6b35", dim: "#cc4422" },
        ok:      { DEFAULT: "#00ff88", dim: "#00cc66" },
        muted:   "#4a5568",
        text:    { DEFAULT: "#c9d1d9", dim: "#8b949e" },
      },
      boxShadow: {
        "glow-accent": "0 0 20px #00d4ff33, 0 0 40px #00d4ff11",
        "glow-warn":   "0 0 20px #ff6b3533",
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4,0,0.6,1) infinite",
        "scan-line":  "scan 4s linear infinite",
        "fade-in":    "fadeIn 0.3s ease-out",
        "slide-up":   "slideUp 0.4s ease-out",
      },
      keyframes: {
        scan: {
          "0%":   { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100vh)" },
        },
        fadeIn: {
          from: { opacity: "0" },
          to:   { opacity: "1" },
        },
        slideUp: {
          from: { opacity: "0", transform: "translateY(12px)" },
          to:   { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
