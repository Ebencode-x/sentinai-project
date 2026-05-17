interface Props {
  label:   string;
  value:   string | number;
  sub?:    string;
  accent?: boolean;
  color?:  "cyan" | "red" | "amber" | "green" | "purple";
}

const COLOR_MAP = {
  cyan:   "var(--cyan)",
  red:    "var(--red)",
  amber:  "var(--amber)",
  green:  "var(--green)",
  purple: "var(--purple)",
};

export default function StatCard({ label, value, sub, accent, color = "cyan" }: Props) {
  const c = accent ? COLOR_MAP[color] : "var(--text-primary)";

  return (
    <div
      className="rounded-lg px-4 py-3 flex flex-col gap-1"
      style={{
        background: "var(--bg-surface)",
        border:     "0.5px solid var(--border)",
      }}
    >
      <p
        className="text-[10px] font-mono tracking-widest uppercase"
        style={{ color: "var(--text-muted)", fontFamily: "'IBM Plex Mono', monospace" }}
      >
        {label}
      </p>
      <p
        className="text-2xl font-display font-bold leading-none tracking-tight"
        style={{ color: c, fontFamily: "'Syne', sans-serif" }}
      >
        {value}
      </p>
      {sub && (
        <p
          className="text-[10px] font-mono"
          style={{ color: "var(--text-muted)", fontFamily: "'IBM Plex Mono', monospace" }}
        >
          {sub}
        </p>
      )}
    </div>
  );
}
