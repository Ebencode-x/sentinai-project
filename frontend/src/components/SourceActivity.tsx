import { useState, type ReactNode } from "react";
import { formatDistanceToNowStrict, parseISO } from "date-fns";
import { Card, CardHeader } from "@/components/Card";
import HoverTip from "@/components/HoverTip";
import { useHoverTip } from "@/hooks/useHoverTip";
import { dayLabel, niceMax } from "@/lib/activity";
import type { ActivityReport, SourceActivity as SourceStats } from "@/api/activity";

const BAR_DAYS = 30;
const BAR_AREA = 28;

interface Props {
  report: ActivityReport | undefined;
  loading: boolean;
  error: boolean;
}

type ShowTip = (el: Element, content: ReactNode) => void;

function lastEventText(iso: string | null): string {
  if (!iso) return "No events yet";
  try {
    return `Last event ${formatDistanceToNowStrict(parseISO(iso), { addSuffix: true })}`;
  } catch {
    return "Last event unknown";
  }
}

function SourceRow({
  source,
  dates,
  onShow,
  onHide,
}: {
  source: SourceStats;
  dates: string[];
  onShow: ShowTip;
  onHide: () => void;
}) {
  const n = Math.min(BAR_DAYS, source.daily.length, dates.length);
  const counts = source.daily.slice(source.daily.length - n);
  const days = dates.slice(dates.length - n);
  const total = counts.reduce((a, b) => a + b, 0);
  const max = niceMax(Math.max(0, ...counts));
  const revoked = source.status === "revoked";
  const seen = lastEventText(source.last_event_at);

  return (
    <li
      className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:gap-6"
      style={{ opacity: revoked ? 0.6 : 1 }}
    >
      <div className="min-w-0 sm:w-56">
        <div className="truncate text-sm font-medium">{source.name}</div>
        <div className="text-xs" style={{ color: "var(--text-muted)" }}>
          {revoked ? `Revoked, ${seen.toLowerCase()}` : seen}
        </div>
      </div>
      <div
        className="flex min-w-0 flex-1 items-end gap-[2px]"
        style={{ height: BAR_AREA }}
        role="img"
        aria-label={`${source.name}: ${total} events in the last ${n} days`}
      >
        {counts.map((c, i) => (
          <div
            key={days[i]}
            className="flex h-full min-w-0 flex-1 items-end"
            onMouseEnter={(e) =>
              onShow(
                e.currentTarget,
                <>
                  <div className="font-medium">
                    {c} event{c === 1 ? "" : "s"}
                  </div>
                  <div style={{ color: "var(--text-muted)" }}>{dayLabel(days[i])}</div>
                </>,
              )
            }
            onMouseLeave={onHide}
          >
            <div
              className="w-full rounded-[2px]"
              style={{
                height: c === 0 ? 2 : Math.max(3, Math.round((c / max) * BAR_AREA)),
                background: c === 0 ? "var(--bg-panel)" : "var(--green)",
              }}
            />
          </div>
        ))}
      </div>
      <div className="text-xs tabular-nums sm:w-28 sm:text-right" style={{ color: "var(--text-secondary)" }}>
        {total} event{total === 1 ? "" : "s"}, {n} days
      </div>
    </li>
  );
}

export default function SourceActivity({ report, loading, error }: Props) {
  const [showRevoked, setShowRevoked] = useState(false);
  const { tip, show, hide } = useHoverTip();

  const sources = report?.sources ?? [];
  const active = sources.filter((s) => s.status === "active");
  const revoked = sources.filter((s) => s.status === "revoked");
  const visible = showRevoked ? [...active, ...revoked] : active;
  const dates = (report?.daily ?? []).map((d) => d.date);

  let body: ReactNode;
  if (loading) {
    body = (
      <div className="p-4">
        <div className="h-16 animate-pulse rounded-md" style={{ background: "var(--bg-panel)" }} />
      </div>
    );
  } else if (error || !report) {
    body = (
      <p className="p-4 text-sm" style={{ color: "var(--text-muted)" }}>
        Could not load source activity.
      </p>
    );
  } else if (sources.length === 0) {
    body = (
      <p className="p-4 text-sm" style={{ color: "var(--text-muted)" }}>
        No log sources connected yet.
      </p>
    );
  } else if (visible.length === 0) {
    body = (
      <p className="p-4 text-sm" style={{ color: "var(--text-muted)" }}>
        No active sources. Revoked sources are hidden.
      </p>
    );
  } else {
    body = (
      <>
        <ul className="py-1">
          {visible.map((s) => (
            <SourceRow key={s.id} source={s} dates={dates} onShow={show} onHide={hide} />
          ))}
        </ul>
        <p className="px-4 pb-3 text-xs" style={{ color: "var(--text-muted)" }}>
          Events received per day, last {BAR_DAYS} days. Each bar is one UTC day.
        </p>
      </>
    );
  }

  return (
    <>
      <Card>
        <CardHeader
          title="Sources"
          action={
            revoked.length > 0 ? (
              <button
                type="button"
                onClick={() => setShowRevoked((v) => !v)}
                className="text-xs hover:underline"
                style={{ color: "var(--text-secondary)" }}
              >
                {showRevoked ? "Hide" : "Show"} revoked ({revoked.length})
              </button>
            ) : undefined
          }
        />
        {body}
      </Card>
      <HoverTip tip={tip} />
    </>
  );
}
