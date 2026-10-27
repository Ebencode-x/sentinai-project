import { formatDistanceToNow, parseISO } from "date-fns";
import { useNavigate } from "react-router";
import { Card, CardHeader } from "@/components/Card";
import { useAudit } from "@/hooks/useAudit";

const LEVEL_COLOR: Record<string, string> = {
  success: "var(--green)",
  warning: "var(--amber)",
  danger: "var(--red)",
  info: "var(--text-muted)",
};

function ago(ts: string | null): string {
  if (!ts) return "";
  try {
    return formatDistanceToNow(parseISO(ts), { addSuffix: true });
  } catch {
    return "";
  }
}

export default function ActivityFeed() {
  const navigate = useNavigate();
  const { data, isLoading, isError } = useAudit(8);

  return (
    <Card className="flex-1">
      <CardHeader
        title="Recent activity"
        action={
          <button
            onClick={() => navigate("/audit")}
            className="text-xs font-medium transition-opacity hover:opacity-80"
            style={{ color: "var(--brand)" }}
          >
            View all
          </button>
        }
      />

      {isLoading && (
        <div className="p-4 flex flex-col gap-3">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-9 rounded-md animate-pulse" style={{ background: "var(--bg-panel)" }} />
          ))}
        </div>
      )}

      {isError && (
        <p className="p-4 text-sm" style={{ color: "var(--red)" }}>
          Could not load activity.
        </p>
      )}

      {data && data.length === 0 && (
        <p className="p-6 text-sm text-center" style={{ color: "var(--text-muted)" }}>
          No activity yet. Events appear here after the first scan.
        </p>
      )}

      {data && data.length > 0 && (
        <ul>
          {data.map((e, i) => (
            <li
              key={e.id}
              className="flex items-start gap-3 px-4 py-3"
              style={{ borderTop: i === 0 ? undefined : "1px solid var(--border)" }}
            >
              <span
                className="mt-1.5 w-2 h-2 rounded-full shrink-0"
                style={{ background: LEVEL_COLOR[e.level] ?? LEVEL_COLOR.info }}
              />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                  {e.title}
                  {e.count > 1 && (
                    <span className="ml-2 text-xs font-normal" style={{ color: "var(--text-muted)" }}>
                      x{e.count}
                    </span>
                  )}
                </p>
                <p className="text-xs truncate" style={{ color: "var(--text-muted)" }}>
                  {e.incident_id}
                  {e.patch_file ? ` · ${e.patch_file}` : ""}
                </p>
                {e.detail && (
                  <p className="text-xs mt-0.5 line-clamp-2" style={{ color: "var(--text-secondary)" }}>
                    {e.detail}
                  </p>
                )}
              </div>
              <span className="text-xs shrink-0 mt-0.5" style={{ color: "var(--text-muted)" }}>
                {ago(e.timestamp)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
