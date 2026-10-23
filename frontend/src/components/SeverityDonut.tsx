import type { Incident } from "@/api/client";
import { Card, CardHeader } from "@/components/Card";

const ORDER = [
  { key: "critical", label: "Critical", color: "var(--red)" },
  { key: "high", label: "High", color: "var(--brand)" },
  { key: "medium", label: "Medium", color: "var(--amber)" },
  { key: "low", label: "Low", color: "var(--green)" },
] as const;

const R = 42;
const C = 2 * Math.PI * R;

export default function SeverityDonut({ incidents }: { incidents: Incident[] }) {
  const total = incidents.length;
  const counts = ORDER.map((o) => incidents.filter((i) => i.severity === o.key).length);

  let acc = 0;
  const segments = ORDER.map((o, idx) => {
    const len = total > 0 ? (counts[idx] / total) * C : 0;
    const seg = { ...o, len, offset: acc };
    acc += len;
    return seg;
  });

  return (
    <Card>
      <CardHeader title="Severity" />
      <div className="p-4 flex items-center gap-6">
        <div className="relative w-28 h-28 shrink-0">
          <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
            <circle cx="50" cy="50" r={R} fill="none" stroke="var(--bg-panel)" strokeWidth="9" />
            {segments.map((s) =>
              s.len > 0 ? (
                <circle
                  key={s.key}
                  cx="50"
                  cy="50"
                  r={R}
                  fill="none"
                  stroke={s.color}
                  strokeWidth="9"
                  strokeDasharray={`${s.len} ${C - s.len}`}
                  strokeDashoffset={-s.offset}
                />
              ) : null
            )}
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-2xl font-semibold leading-none">{total}</span>
            <span className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>total</span>
          </div>
        </div>
        <ul className="flex-1 flex flex-col gap-2">
          {ORDER.map((o, idx) => (
            <li key={o.key} className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-2" style={{ color: "var(--text-secondary)" }}>
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: o.color }} />
                {o.label}
              </span>
              <span className="font-medium">{counts[idx]}</span>
            </li>
          ))}
        </ul>
      </div>
    </Card>
  );
}
