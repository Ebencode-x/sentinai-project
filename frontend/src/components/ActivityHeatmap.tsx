import { useMemo } from "react";
import { eachDayOfInterval, format, parseISO, startOfWeek, subWeeks } from "date-fns";
import { Card, CardHeader } from "@/components/Card";
import { useAudit } from "@/hooks/useAudit";

const WEEKS = 26;
const LEVEL_PCT = [0, 30, 50, 75, 100];

function level(n: number): number {
  if (n === 0) return 0;
  if (n <= 1) return 1;
  if (n <= 3) return 2;
  if (n <= 7) return 3;
  return 4;
}

export default function ActivityHeatmap() {
  const { data, isLoading } = useAudit(200);

  const { days, total, activeDays } = useMemo(() => {
    const today = new Date();
    const start = startOfWeek(subWeeks(today, WEEKS - 1));
    const counts = new Map<string, number>();
    for (const e of data ?? []) {
      if (!e.timestamp) continue;
      try {
        const k = format(parseISO(e.timestamp), "yyyy-MM-dd");
        counts.set(k, (counts.get(k) ?? 0) + e.count);
      } catch {
        /* skip bad timestamp */
      }
    }
    const days = eachDayOfInterval({ start, end: today }).map((d) => {
      const key = format(d, "yyyy-MM-dd");
      return { key, label: format(d, "MMM d, yyyy"), n: counts.get(key) ?? 0 };
    });
    return {
      days,
      total: days.reduce((a, d) => a + d.n, 0),
      activeDays: days.filter((d) => d.n > 0).length,
    };
  }, [data]);

  return (
    <Card>
      <CardHeader
        title="Activity"
        action={
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
            {total} actions across {activeDays} active days
          </span>
        }
      />
      <div className="p-4 overflow-x-auto">
        {isLoading ? (
          <div className="h-[105px] rounded-md animate-pulse" style={{ background: "var(--bg-panel)" }} />
        ) : (
          <div
            className="grid"
            style={{
              gridTemplateRows: "repeat(7, 12px)",
              gridAutoFlow: "column",
              gridAutoColumns: "12px",
              gap: "3px",
              width: "max-content",
            }}
          >
            {days.map((d) => {
              const l = level(d.n);
              return (
                <div
                  key={d.key}
                  title={`${d.n} action${d.n === 1 ? "" : "s"} on ${d.label}`}
                  className="rounded-[3px]"
                  style={{
                    background:
                      l === 0
                        ? "var(--bg-panel)"
                        : `color-mix(in srgb, var(--green) ${LEVEL_PCT[l]}%, transparent)`,
                  }}
                />
              );
            })}
          </div>
        )}
        <p className="text-xs mt-3" style={{ color: "var(--text-muted)" }}>
          Built from the audit log. Repeated identical events count once per occurrence.
        </p>
      </div>
    </Card>
  );
}
