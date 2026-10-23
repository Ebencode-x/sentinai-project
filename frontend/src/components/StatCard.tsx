interface Props {
  label:   string;
  value:   string | number;
  sub?:    string;
  accent?: boolean;
  color?:  "cyan" | "red" | "amber" | "green" | "purple";
}

const COLOR_MAP = {
  cyan:   "var(--brand)",
  red:    "var(--red)",
  amber:  "var(--amber)",
  green:  "var(--green)",
  purple: "var(--purple)",
};

export default function StatCard({ label, value, sub, accent, color = "cyan" }: Props) {
  const c = accent ? COLOR_MAP[color] : "var(--text-primary)";
  return (
    <div
      className="rounded-lg p-4 flex flex-col gap-1"
      style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
    >
      <p className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>{label}</p>
      <p className="text-2xl font-semibold leading-tight tabular-nums" style={{ color: c }}>{value}</p>
      {sub && <p className="text-xs" style={{ color: "var(--text-muted)" }}>{sub}</p>}
    </div>
  );
}
