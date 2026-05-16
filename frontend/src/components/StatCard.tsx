interface Props {
  label: string;
  value: string | number;
  sub?: string;
  accent?: boolean;
}

export default function StatCard({ label, value, sub, accent }: Props) {
  return (
    <div className="border border-bg-border bg-bg-card px-5 py-4 rounded-sm">
      <div className="text-xs text-muted tracking-widest mb-2">{label}</div>
      <div className={`text-2xl font-display font-medium ${accent ? "text-accent glow-text" : "text-text"}`}>
        {value}
      </div>
      {sub && <div className="text-xs text-muted mt-1">{sub}</div>}
    </div>
  );
}
