const SEV: Record<string, { color: string; bg: string; border: string }> = {
  critical: { color: "var(--red)",    bg: "var(--red-dim)",    border: "var(--red)"    },
  high:     { color: "var(--amber)",  bg: "var(--amber-dim)",  border: "var(--amber)"  },
  medium:   { color: "var(--purple)", bg: "var(--purple-dim)", border: "var(--purple)" },
  low:      { color: "var(--green)",  bg: "var(--green-dim)",  border: "var(--green)"  },
};

export default function SeverityBadge({ level }: { level: string }) {
  const s = SEV[level] ?? SEV.low;
  return (
    <span style={{
      display: "inline-block",
      fontFamily: "'IBM Plex Mono', monospace", fontSize: "9px",
      letterSpacing: "0.12em", textTransform: "uppercase",
      padding: "2px 7px", borderRadius: "3px",
      color: s.color, background: s.bg, border: `0.5px solid ${s.border}`,
    }}>
      {level}
    </span>
  );
}
