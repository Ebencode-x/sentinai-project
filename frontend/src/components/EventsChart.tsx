import { useState } from "react";
import { format, parseISO } from "date-fns";
import type { ActivityReport } from "@/api/activity";
import { Card, CardHeader } from "@/components/Card";
import HoverTip from "@/components/HoverTip";
import { useHoverTip } from "@/hooks/useHoverTip";
import { dayLabel, niceMax, type Range } from "@/lib/activity";

const HEIGHT = 160;
const COL = 10;
const BAR = 7;

function shortDate(date: string): string {
  try {
    return format(parseISO(date), "MMM d");
  } catch {
    return date;
  }
}

function axisValue(n: number): string {
  return Number.isInteger(n) ? n.toLocaleString("en-US") : n.toFixed(1);
}

interface Props {
  report: ActivityReport | undefined;
  loading: boolean;
  error: boolean;
  range: Range;
}

export default function EventsChart({ report, loading, error, range }: Props) {
  const { tip, show, hide } = useHoverTip();
  const [hover, setHover] = useState<number | null>(null);

  const ready = !!report && !loading;
  const days = (report?.daily ?? []).slice(-range);
  const total = days.reduce((sum, d) => sum + d.events, 0);
  const max = niceMax(Math.max(0, ...days.map((d) => d.events)));
  const empty = ready && total === 0;
  const width = Math.max(days.length, 1) * COL;
  const mid = days[Math.floor(days.length / 2)];

  let note: string | null = null;
  if (error) note = "Could not load activity";
  else if (!ready) note = "Loading";
  else if (empty) note = `No events received in the last ${range} days. Send events with an ingest key and they will appear here.`;

  return (
    <Card>
      <CardHeader
        title="Events received"
        action={
          <span className="text-xs tabular-nums" style={{ color: "var(--text-muted)" }}>
            {ready ? `${total.toLocaleString("en-US")} in the last ${range} days` : ""}
          </span>
        }
      />
      <div className="px-4 py-4">
        <div className="flex gap-3">
          <div
            className="flex flex-col justify-between text-xs text-right tabular-nums w-8 shrink-0"
            style={{ height: HEIGHT, color: "var(--text-muted)" }}
            aria-hidden="true"
          >
            <span>{axisValue(max)}</span>
            <span>{axisValue(max / 2)}</span>
            <span>0</span>
          </div>
          <div className="relative flex-1 min-w-0">
            <svg
              viewBox={`0 0 ${width} 100`}
              preserveAspectRatio="none"
              className="block w-full"
              style={{ height: HEIGHT }}
              role="img"
              aria-label={`Events received per day, last ${range} days, ${total} in total`}
            >
              {[0, 50, 100].map((y) => (
                <line
                  key={y}
                  x1={0}
                  x2={width}
                  y1={y}
                  y2={y}
                  stroke="var(--border)"
                  strokeWidth={1}
                  vectorEffect="non-scaling-stroke"
                />
              ))}
              {ready &&
                days.map((d, i) => {
                  const h = d.events > 0 ? Math.max((d.events / max) * 100, 2) : 0;
                  return (
                    <g key={d.date}>
                      <rect
                        x={i * COL}
                        y={0}
                        width={COL}
                        height={100}
                        fill={hover === i ? "var(--bg-panel)" : "transparent"}
                        onMouseEnter={(e) => {
                          setHover(i);
                          show(
                            e.currentTarget,
                            <div className="flex flex-col gap-0.5 tabular-nums">
                              <span className="font-semibold">{dayLabel(d.date)}</span>
                              <span>{d.events.toLocaleString("en-US")} events</span>
                              <span>{d.new_incidents} new incidents</span>
                              <span>{d.resolved} resolved</span>
                            </div>,
                          );
                        }}
                        onMouseLeave={() => {
                          setHover(null);
                          hide();
                        }}
                      />
                      {h > 0 && (
                        <rect
                          x={i * COL + (COL - BAR) / 2}
                          y={100 - h}
                          width={BAR}
                          height={h}
                          fill="var(--brand)"
                          pointerEvents="none"
                        />
                      )}
                    </g>
                  );
                })}
            </svg>
            {note && (
              <div
                className="absolute inset-0 flex items-center justify-center px-6 text-center text-sm"
                style={{ color: "var(--text-muted)" }}
              >
                {note}
              </div>
            )}
          </div>
        </div>
        {days.length > 0 && (
          <div
            className="flex justify-between text-xs tabular-nums mt-2 pl-11"
            style={{ color: "var(--text-muted)" }}
            aria-hidden="true"
          >
            <span>{shortDate(days[0].date)}</span>
            <span>{mid ? shortDate(mid.date) : ""}</span>
            <span>{shortDate(days[days.length - 1].date)}</span>
          </div>
        )}
      </div>
      <HoverTip tip={tip} />
    </Card>
  );
}
