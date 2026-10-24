const SEV: Record<string, { color: string; bg: string; label: string }> = {
  critical: { color: "var(--red)",    bg: "var(--red-dim)",    label: "Critical" },
  high:     { color: "var(--brand)",  bg: "var(--brand-dim)",  label: "High" },
  medium:   { color: "var(--amber)",  bg: "var(--amber-dim)",  label: "Medium" },
  low:      { color: "var(--green)",  bg: "var(--green-dim)",  label: "Low" },
};

export default function SeverityBadge({ level }: { level: string }) {
  const s = SEV[level] ?? SEV.low;
  return (
    <span
      className="inline-block text-xs font-medium rounded-full px-2.5 py-0.5"
      style={{ color: s.color, background: s.bg }}
    >
      {s.label}
    </span>
  );
}
