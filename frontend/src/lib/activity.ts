import { format, parseISO } from "date-fns";
import type { DayActivity, SourceActivity } from "@/api/activity";

export type Range = 7 | 30 | 90;
export const RANGES: Range[] = [7, 30, 90];

export interface WindowTotals {
  events: number;
  newIncidents: number;
  resolved: number;
}

/** Totals for the last `range` days. back = 1 gives the window right before it. */
export function windowTotals(daily: DayActivity[], range: number, back = 0): WindowTotals {
  const end = daily.length - back * range;
  const start = Math.max(0, end - range);
  const slice = end > start ? daily.slice(start, end) : [];
  return slice.reduce<WindowTotals>(
    (sum, d) => ({
      events: sum.events + d.events,
      newIncidents: sum.newIncidents + d.new_incidents,
      resolved: sum.resolved + d.resolved,
    }),
    { events: 0, newIncidents: 0, resolved: 0 },
  );
}

export function compareText(current: number, previous: number, range: number): string {
  const label = `previous ${range} days`;
  const diff = current - previous;
  if (diff === 0) return `same as ${label}`;
  return `${diff > 0 ? "+" : "-"}${Math.abs(diff)} vs ${label}`;
}

/** A round upper bound for a chart axis, never below 4 so a quiet chart stays readable. */
export function niceMax(value: number): number {
  if (value <= 4) return 4;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  for (const step of [1, 2, 2.5, 5, 10]) {
    if (value <= step * magnitude) return step * magnitude;
  }
  return 10 * magnitude;
}

export function dayLabel(date: string): string {
  try {
    return format(parseISO(date), "EEE, MMM d, yyyy");
  } catch {
    return date;
  }
}

export function activeSourcesSince(
  sources: SourceActivity[],
  hours = 24,
  now: number = Date.now(),
): number {
  const cutoff = now - hours * 3_600_000;
  return sources.filter(
    (s) => s.status === "active" && s.last_event_at && new Date(s.last_event_at).getTime() >= cutoff,
  ).length;
}

/** The UTC calendar day (yyyy-MM-dd) of a timestamp. A time without a zone is read as UTC. */
export function utcDay(ts: string | null | undefined): string | null {
  if (!ts) return null;
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(ts);
  const ms = new Date(hasZone ? ts : `${ts}Z`).getTime();
  if (Number.isNaN(ms)) return null;
  return new Date(ms).toISOString().slice(0, 10);
}
