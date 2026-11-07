import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { getDay, getMonth, parseISO } from "date-fns";
import { Card, CardHeader } from "@/components/Card";
import HoverTip from "@/components/HoverTip";
import { useHoverTip } from "@/hooks/useHoverTip";
import { dayLabel } from "@/lib/activity";
import type { ActivityReport, DayActivity } from "@/api/activity";

const CELL = 12;
const GAP = 3;
const LEVEL_PCT = [0, 30, 50, 75, 100];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const WEEKDAYS: [number, string][] = [
  [1, "Mon"],
  [3, "Wed"],
  [5, "Fri"],
];
const KEY_STEP: Record<string, number> = { ArrowLeft: -7, ArrowRight: 7, ArrowUp: -1, ArrowDown: 1 };

interface Props {
  report: ActivityReport | undefined;
  loading: boolean;
  error: boolean;
  selected: string | null;
  onSelect: (date: string) => void;
}

function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

function value(d: DayActivity): number {
  return d.events + d.new_incidents;
}

/** 0 for a quiet day, 1 to 4 scaled to the busiest day in the window. */
function level(n: number, max: number): number {
  if (n <= 0 || max <= 0) return 0;
  return Math.min(4, Math.max(1, Math.ceil((n / max) * 4)));
}

function fill(l: number): string {
  return l === 0 ? "var(--bg-panel)" : `color-mix(in srgb, var(--green) ${LEVEL_PCT[l]}%, transparent)`;
}

export default function ActivityHeatmap({ report, loading, error, selected, onSelect }: Props) {
  const { tip, show, hide } = useHoverTip();
  const [focusIdx, setFocusIdx] = useState<number | null>(null);
  const cellRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const scroller = useRef<HTMLDivElement>(null);
  const daily = report?.daily;

  const layout = useMemo(() => {
    const list = daily ?? [];
    if (list.length === 0) return null;
    const offset = getDay(parseISO(list[0].date));
    const max = Math.max(0, ...list.map(value));
    const cells = list.map((day, idx) => ({
      day,
      idx,
      col: Math.floor((offset + idx) / 7),
      row: (offset + idx) % 7,
    }));
    const months: { col: number; label: string }[] = [];
    let prev = -1;
    for (const c of cells) {
      const m = getMonth(parseISO(c.day.date));
      if (m !== prev) {
        months.push({ col: c.col, label: MONTHS[m] });
        prev = m;
      }
    }
    // A label squeezed against the next one at the left edge would overlap it.
    if (months.length > 1 && months[1].col - months[0].col < 3) months.shift();
    return { cells, max, months, cols: cells[cells.length - 1].col + 1 };
  }, [daily]);

  const cols = layout?.cols ?? 0;
  const count = layout?.cells.length ?? 0;
  const activeIdx = focusIdx ?? count - 1;

  // Start scrolled to the right so today is visible on narrow screens.
  useEffect(() => {
    const el = scroller.current;
    if (el) el.scrollLeft = el.scrollWidth;
  }, [cols]);

  function showTip(el: Element, d: DayActivity) {
    show(
      el,
      <>
        <div className="font-medium">{plural(d.events, "event")}</div>
        <div style={{ color: "var(--text-secondary)" }}>
          {plural(d.new_incidents, "new incident")}, {d.resolved} resolved
        </div>
        <div style={{ color: "var(--text-muted)" }}>{dayLabel(d.date)}</div>
      </>,
    );
  }

  function onKey(e: KeyboardEvent<HTMLButtonElement>, idx: number) {
    if (!(e.key in KEY_STEP)) return;
    e.preventDefault();
    const next = Math.min(count - 1, Math.max(0, idx + KEY_STEP[e.key]));
    setFocusIdx(next);
    cellRefs.current[next]?.focus();
  }

  let body: ReactNode;
  if (loading) {
    body = (
      <div className="p-4">
        <div className="h-[140px] animate-pulse rounded-md" style={{ background: "var(--bg-panel)" }} />
      </div>
    );
  } else if (error || !report) {
    body = (
      <p className="p-4 text-sm" style={{ color: "var(--text-muted)" }}>
        Could not load activity.
      </p>
    );
  } else if (!layout) {
    body = (
      <p className="p-4 text-sm" style={{ color: "var(--text-muted)" }}>
        No activity data yet.
      </p>
    );
  } else {
    const { totals } = report;
    body = (
      <div className="p-4">
        <div ref={scroller} className="overflow-x-auto pb-1">
          <div
            role="group"
            aria-label="Daily activity heatmap"
            className="grid"
            style={{
              gridTemplateColumns: `28px repeat(${layout.cols}, ${CELL}px)`,
              gridTemplateRows: `14px repeat(7, ${CELL}px)`,
              gap: GAP,
              width: "max-content",
            }}
          >
            {layout.months.map((m) => (
              <span
                key={m.col}
                className="whitespace-nowrap text-[11px]"
                style={{ gridRow: 1, gridColumn: m.col + 2, lineHeight: "14px", color: "var(--text-muted)" }}
              >
                {m.label}
              </span>
            ))}
            {WEEKDAYS.map(([row, label]) => (
              <span
                key={label}
                className="text-[11px]"
                style={{ gridRow: row + 2, gridColumn: 1, lineHeight: `${CELL}px`, color: "var(--text-muted)" }}
              >
                {label}
              </span>
            ))}
            {layout.cells.map(({ day, idx, col, row }) => {
              const isSelected = selected === day.date;
              return (
                <button
                  key={day.date}
                  type="button"
                  ref={(el) => {
                    cellRefs.current[idx] = el;
                  }}
                  tabIndex={idx === activeIdx ? 0 : -1}
                  aria-label={`${dayLabel(day.date)}: ${plural(day.events, "event")}, ${plural(day.new_incidents, "new incident")}, ${day.resolved} resolved`}
                  aria-pressed={isSelected}
                  onClick={() => {
                    setFocusIdx(idx);
                    onSelect(day.date);
                  }}
                  onKeyDown={(e) => onKey(e, idx)}
                  onMouseEnter={(e) => showTip(e.currentTarget, day)}
                  onMouseLeave={hide}
                  onFocus={(e) => {
                    setFocusIdx(idx);
                    showTip(e.currentTarget, day);
                  }}
                  onBlur={hide}
                  className="block rounded-[3px] p-0"
                  style={{
                    gridRow: row + 2,
                    gridColumn: col + 2,
                    background: fill(level(value(day), layout.max)),
                    boxShadow: isSelected ? "0 0 0 2px var(--text-primary)" : undefined,
                  }}
                />
              );
            })}
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            Longest streak {plural(totals.longest_streak, "day")}, current streak{" "}
            {plural(totals.current_streak, "day")}. Select a day for details.
          </p>
          <div className="flex items-center gap-1.5 text-xs" style={{ color: "var(--text-muted)" }}>
            <span>Less</span>
            {[0, 1, 2, 3, 4].map((l) => (
              <span
                key={l}
                className="inline-block rounded-[3px]"
                style={{ width: CELL, height: CELL, background: fill(l) }}
              />
            ))}
            <span>More</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      <Card>
        <CardHeader
          title="Activity"
          action={
            report && !loading && !error ? (
              <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                {plural(report.totals.events, "event")} across {plural(report.totals.active_days, "active day")}
              </span>
            ) : undefined
          }
        />
        {body}
      </Card>
      <HoverTip tip={tip} />
    </>
  );
}
