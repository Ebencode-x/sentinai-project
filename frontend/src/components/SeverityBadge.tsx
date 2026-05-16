import clsx from "clsx";

const MAP = {
  critical: "border-red-500   text-red-400   bg-red-500/5",
  high:     "border-warn      text-warn      bg-warn/5",
  medium:   "border-yellow-500 text-yellow-400 bg-yellow-500/5",
  low:      "border-ok        text-ok        bg-ok/5",
} as const;

type Severity = keyof typeof MAP;

export default function SeverityBadge({ level }: { level: Severity }) {
  return (
    <span className={clsx(
      "inline-block border text-[10px] font-display tracking-widest px-2 py-0.5 rounded-sm uppercase",
      MAP[level] ?? MAP.low
    )}>
      {level}
    </span>
  );
}
