import { Fragment, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { format, parseISO } from "date-fns";
import { ChevronRight, ExternalLink, Search, X } from "lucide-react";
import { api, type Suggestion } from "@/api/client";
import { archiveEvents, deleteEvents, restoreEvents, type AuditEvent } from "@/api/audit";
import { useAudit } from "@/hooks/useAudit";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/components/Toast";
import { Card } from "@/components/Card";

type Tab = "audit" | "suggestions";
type LevelFilter = "all" | AuditEvent["level"];

const LEVEL_STYLE: Record<AuditEvent["level"], { color: string; bg: string; label: string }> = {
  success: { color: "var(--green)", bg: "var(--green-dim)", label: "Success" },
  warning: { color: "var(--amber)", bg: "var(--amber-dim)", label: "Warning" },
  danger: { color: "var(--red)", bg: "var(--red-dim)", label: "Denied" },
  info: { color: "var(--text-secondary)", bg: "var(--bg-panel)", label: "Info" },
};

const LEVEL_FILTERS: { key: LevelFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "success", label: "Success" },
  { key: "warning", label: "Warning" },
  { key: "danger", label: "Denied" },
  { key: "info", label: "Info" },
];

function fmt(ts: string | null | undefined): string {
  if (!ts) return "n/a";
  try {
    return format(parseISO(ts), "MMM d, HH:mm");
  } catch {
    return "n/a";
  }
}

function pctOf(v: number | null | undefined): number | null {
  return v == null ? null : Math.round(v * 100);
}

function confColor(p: number): string {
  return p >= 80 ? "var(--green)" : p >= 50 ? "var(--amber)" : "var(--red)";
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className="px-3 py-1 rounded-full text-xs font-medium transition-colors"
      style={{
        background: active ? "var(--bg-hover)" : "transparent",
        color: active ? "var(--text-primary)" : "var(--text-secondary)",
      }}
    >
      {children}
    </button>
  );
}

function SearchBox({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder: string }) {
  return (
    <div
      className="flex items-center gap-2 rounded-md px-2.5 h-8 min-w-[220px]"
      style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}
    >
      <Search size={14} style={{ color: "var(--text-muted)" }} />
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="bg-transparent outline-hidden text-sm w-full"
        style={{ color: "var(--text-primary)" }}
      />
      {value && (
        <button onClick={() => onChange("")} aria-label="Clear search" style={{ color: "var(--text-muted)" }}>
          <X size={14} />
        </button>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <p className="text-xs mb-0.5" style={{ color: "var(--text-muted)" }}>{label}</p>
      <div className="text-sm wrap-break-word" style={{ color: "var(--text-primary)" }}>{children}</div>
    </div>
  );
}

function Message({ text, tone = "muted" }: { text: string; tone?: "muted" | "error" }) {
  return (
    <p
      className="p-8 text-sm text-center"
      style={{ color: tone === "error" ? "var(--red)" : "var(--text-muted)" }}
    >
      {text}
    </p>
  );
}

function SkeletonRows() {
  return (
    <div className="p-4 flex flex-col gap-2">
      {[0, 1, 2, 3, 4].map((i) => (
        <div key={i} className="h-10 rounded-md animate-pulse" style={{ background: "var(--bg-panel)" }} />
      ))}
    </div>
  );
}

type Action = "archive" | "restore" | "delete";

const DONE: Record<Action, string> = {
  archive: "archived",
  restore: "restored",
  delete: "deleted",
};

function ActionLink({
  onClick,
  disabled,
  tone = "default",
  children,
}: {
  onClick: () => void;
  disabled?: boolean;
  tone?: "default" | "danger" | "muted";
  children: React.ReactNode;
}) {
  const color =
    tone === "danger" ? "var(--red)" : tone === "muted" ? "var(--text-muted)" : "var(--text-primary)";
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="text-xs font-medium hover:underline disabled:opacity-50 disabled:no-underline"
      style={{ color }}
    >
      {children}
    </button>
  );
}

/* Audit log tab */

function AuditTab() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const qc = useQueryClient();
  const { toast } = useToast();

  const [archivedView, setArchivedView] = useState(false);
  const { data, isLoading, isError } = useAudit(200, archivedView);
  const [level, setLevel] = useState<LevelFilter>("all");
  const [q, setQ] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [confirming, setConfirming] = useState(false);

  const events = useMemo(() => data ?? [], [data]);
  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return events.filter((e) => {
      if (level !== "all" && e.level !== level) return false;
      if (!needle) return true;
      return [e.title, e.incident_id, e.patch_file, e.detail, e.provider, e.model]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(needle));
    });
  }, [events, level, q]);

  const selectable = useMemo(() => rows.filter((e) => e.row_ids.length > 0), [rows]);
  const selectedEvents = useMemo(
    () => events.filter((e) => selected.includes(e.id)),
    [events, selected]
  );
  const selectedIds = useMemo(() => selectedEvents.flatMap((e) => e.row_ids), [selectedEvents]);
  const allSelected = selectable.length > 0 && selectable.every((e) => selected.includes(e.id));

  const act = useMutation({
    mutationFn: ({ kind, ids }: { kind: Action; ids: number[] }) =>
      kind === "archive" ? archiveEvents(ids) : kind === "restore" ? restoreEvents(ids) : deleteEvents(ids),
    onSuccess: (changed, { kind }) => {
      qc.invalidateQueries({ queryKey: ["audit"] });
      setSelected([]);
      setConfirming(false);
      toast(`${changed} event${changed === 1 ? "" : "s"} ${DONE[kind]}`, "ok");
    },
    onError: () => toast("Action failed", "error"),
  });

  function switchView(next: boolean) {
    setArchivedView(next);
    setSelected([]);
    setConfirming(false);
    setOpenId(null);
  }

  function toggle(id: string) {
    setConfirming(false);
    setSelected((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));
  }

  function toggleAll() {
    setConfirming(false);
    setSelected(allSelected ? [] : selectable.map((e) => e.id));
  }

  const colCount = isAdmin ? 7 : 6;
  const emptyText = archivedView
    ? "No archived events."
    : events.length === 0
      ? "No audit events yet. They appear after the first scan."
      : "No events match this filter.";

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2 px-4 py-3" style={{ borderBottom: "1px solid var(--border)" }}>
        <div className="flex flex-wrap gap-1">
          {LEVEL_FILTERS.map((f) => (
            <Chip key={f.key} active={level === f.key} onClick={() => setLevel(f.key)}>{f.label}</Chip>
          ))}
          <Chip active={archivedView} onClick={() => switchView(!archivedView)}>Archived</Chip>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
            {rows.length} of {events.length} events
          </span>
          <SearchBox value={q} onChange={setQ} placeholder="Search events" />
        </div>
      </div>

      {isAdmin && selectedEvents.length > 0 && (
        <div
          className="flex flex-wrap items-center gap-4 px-4 py-2"
          style={{ borderBottom: "1px solid var(--border)", background: "var(--bg-panel)" }}
        >
          <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
            {selectedEvents.length} selected
          </span>
          {confirming ? (
            <>
              <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
                Delete {selectedEvents.length} permanently? This cannot be undone.
              </span>
              <ActionLink
                tone="danger"
                disabled={act.isPending}
                onClick={() => act.mutate({ kind: "delete", ids: selectedIds })}
              >
                Delete
              </ActionLink>
              <ActionLink tone="muted" onClick={() => setConfirming(false)}>Cancel</ActionLink>
            </>
          ) : (
            <>
              {archivedView ? (
                <>
                  <ActionLink
                    disabled={act.isPending}
                    onClick={() => act.mutate({ kind: "restore", ids: selectedIds })}
                  >
                    Restore
                  </ActionLink>
                  <ActionLink tone="danger" disabled={act.isPending} onClick={() => setConfirming(true)}>
                    Delete permanently
                  </ActionLink>
                </>
              ) : (
                <ActionLink
                  disabled={act.isPending}
                  onClick={() => act.mutate({ kind: "archive", ids: selectedIds })}
                >
                  Archive
                </ActionLink>
              )}
              <ActionLink tone="muted" onClick={() => setSelected([])}>Clear</ActionLink>
            </>
          )}
        </div>
      )}

      {isLoading ? (
        <SkeletonRows />
      ) : isError ? (
        <Message tone="error" text="Could not load the audit log." />
      ) : rows.length === 0 ? (
        <Message text={emptyText} />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[680px]">
            <thead>
              <tr style={{ color: "var(--text-muted)" }}>
                {isAdmin && (
                  <th className="w-10 pl-4 text-left">
                    <input
                      type="checkbox"
                      checked={allSelected}
                      onChange={toggleAll}
                      disabled={selectable.length === 0}
                      aria-label="Select all events"
                      style={{ accentColor: "var(--brand)" }}
                    />
                  </th>
                )}
                <th className="w-8" />
                <th className="text-left font-medium text-xs px-2 py-2">Event</th>
                <th className="text-left font-medium text-xs px-2 py-2 w-28">Status</th>
                <th className="text-left font-medium text-xs px-2 py-2 w-24">Risk</th>
                <th className="text-left font-medium text-xs px-2 py-2 w-28">Confidence</th>
                <th className="text-right font-medium text-xs px-4 py-2 w-32">Time</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((e) => {
                const st = LEVEL_STYLE[e.level] ?? LEVEL_STYLE.info;
                const open = openId === e.id;
                const p = pctOf(e.confidence);
                const picked = selected.includes(e.id);
                return (
                  <Fragment key={e.id}>
                    <tr
                      onClick={() => setOpenId(open ? null : e.id)}
                      className="cursor-pointer transition-colors hover:bg-(--bg-panel)"
                      style={{ borderTop: "1px solid var(--border)", background: open ? "var(--bg-panel)" : undefined }}
                    >
                      {isAdmin && (
                        <td className="pl-4" onClick={(ev) => ev.stopPropagation()}>
                          <input
                            type="checkbox"
                            checked={picked}
                            onChange={() => toggle(e.id)}
                            disabled={e.row_ids.length === 0}
                            aria-label="Select event"
                            style={{ accentColor: "var(--brand)" }}
                          />
                        </td>
                      )}
                      <td className="pl-3">
                        <ChevronRight
                          size={14}
                          className="transition-transform"
                          style={{ color: "var(--text-muted)", transform: open ? "rotate(90deg)" : undefined }}
                        />
                      </td>
                      <td className="px-2 py-3 max-w-0">
                        <p className="truncate font-medium">
                          {e.title}
                          {e.count > 1 && (
                            <span className="ml-2 text-xs font-normal" style={{ color: "var(--text-muted)" }}>x{e.count}</span>
                          )}
                        </p>
                        <p className="truncate text-xs" style={{ color: "var(--text-muted)" }}>
                          {e.incident_id}{e.patch_file ? ` · ${e.patch_file}` : ""}
                        </p>
                      </td>
                      <td className="px-2 py-3">
                        <span
                          className="inline-block text-xs font-medium rounded-full px-2.5 py-0.5"
                          style={{ color: st.color, background: st.bg }}
                        >
                          {st.label}
                        </span>
                      </td>
                      <td className="px-2 py-3 text-xs capitalize" style={{ color: "var(--text-secondary)" }}>
                        {e.risk_tier ?? "n/a"}
                      </td>
                      <td className="px-2 py-3 text-xs">
                        {p == null ? (
                          <span style={{ color: "var(--text-muted)" }}>n/a</span>
                        ) : (
                          <span className="font-medium" style={{ color: confColor(p) }}>{p}%</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right text-xs" style={{ color: "var(--text-muted)" }}>
                        {fmt(e.timestamp)}
                      </td>
                    </tr>
                    {open && (
                      <tr style={{ background: "var(--bg-base)" }}>
                        <td colSpan={colCount} className="px-4 py-4">
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <Field label="Incident ID">{e.incident_id ?? "n/a"}</Field>
                            <Field label="Patch file">{e.patch_file ?? "n/a"}</Field>
                            <Field label="Provider">{e.provider ?? "n/a"}</Field>
                            <Field label="Model">{e.model ?? "n/a"}</Field>
                            <Field label="Source">{e.source ?? "n/a"}</Field>
                            <Field label="Pull request">
                              {e.pr_url ? (
                                <a
                                  href={e.pr_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="inline-flex items-center gap-1 hover:underline"
                                  style={{ color: "var(--brand)" }}
                                >
                                  Open <ExternalLink size={12} />
                                </a>
                              ) : (
                                "None"
                              )}
                            </Field>
                            <Field label="Occurrences">{e.count}</Field>
                            {e.archived_at && (
                              <Field label="Archived">
                                {fmt(e.archived_at)}
                                {e.archived_by ? ` by ${e.archived_by}` : ""}
                              </Field>
                            )}
                          </div>
                          {e.detail && (
                            <div className="mt-4">
                              <Field label="Details">{e.detail}</Field>
                            </div>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

/* Suggestions tab */

function SuggestionsTab() {
  const [q, setQ] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);

  const { data = [], isLoading, isError } = useQuery({
    queryKey: ["suggestions"],
    queryFn: () => api.suggestions().then((r) => r.data),
    refetchInterval: 30_000,
  });

  const rows: Suggestion[] = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return data;
    return data.filter(
      (s) =>
        s.source.toLowerCase().includes(needle) ||
        s.summary.toLowerCase().includes(needle) ||
        s.id.toLowerCase().includes(needle)
    );
  }, [data, q]);

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2 px-4 py-3" style={{ borderBottom: "1px solid var(--border)" }}>
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
          {rows.length} of {data.length} suggestions
        </span>
        <div className="ml-auto">
          <SearchBox value={q} onChange={setQ} placeholder="Source, summary or id" />
        </div>
      </div>

      {isLoading ? (
        <SkeletonRows />
      ) : isError ? (
        <Message tone="error" text="Could not load suggestions." />
      ) : rows.length === 0 ? (
        <Message text={data.length === 0 ? "No suggestions yet." : "No suggestions match your search."} />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[620px]">
            <thead>
              <tr style={{ color: "var(--text-muted)" }}>
                <th className="w-8" />
                <th className="text-left font-medium text-xs px-2 py-2">Summary</th>
                <th className="text-left font-medium text-xs px-2 py-2 w-24">Source</th>
                <th className="text-left font-medium text-xs px-2 py-2 w-28">Confidence</th>
                <th className="text-right font-medium text-xs px-4 py-2 w-32">Created</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((s) => {
                const open = openId === s.id;
                const p = Math.round(s.confidence * 100);
                return (
                  <Fragment key={s.id}>
                    <tr
                      onClick={() => setOpenId(open ? null : s.id)}
                      className="cursor-pointer transition-colors hover:bg-(--bg-panel)"
                      style={{ borderTop: "1px solid var(--border)", background: open ? "var(--bg-panel)" : undefined }}
                    >
                      <td className="pl-3">
                        <ChevronRight
                          size={14}
                          className="transition-transform"
                          style={{ color: "var(--text-muted)", transform: open ? "rotate(90deg)" : undefined }}
                        />
                      </td>
                      <td className="px-2 py-3 max-w-0">
                        <p className="truncate font-medium">{s.summary}</p>
                        <p className="truncate text-xs" style={{ color: "var(--text-muted)" }}>{s.id}</p>
                      </td>
                      <td className="px-2 py-3 text-xs capitalize" style={{ color: "var(--text-secondary)" }}>{s.source}</td>
                      <td className="px-2 py-3 text-xs font-medium" style={{ color: confColor(p) }}>{p}%</td>
                      <td className="px-4 py-3 text-right text-xs" style={{ color: "var(--text-muted)" }}>
                        {fmt(s.created_at_utc)}
                      </td>
                    </tr>
                    {open && (
                      <tr style={{ background: "var(--bg-base)" }}>
                        <td colSpan={5} className="px-4 py-4">
                          <Field label="Full summary">{s.summary}</Field>
                          <p className="text-xs mt-3 break-all" style={{ color: "var(--text-muted)" }}>ID: {s.id}</p>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

/* Page */

export default function AuditExplorer() {
  const [tab, setTab] = useState<Tab>("audit");

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Audit</h1>
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          Every action SentinAI takes, and the remediation suggestions behind it
        </p>
      </div>

      <div className="flex gap-1" style={{ borderBottom: "1px solid var(--border)" }}>
        {([["audit", "Audit log"], ["suggestions", "Suggestions"]] as [Tab, string][]).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className="px-3 py-2 text-sm font-medium -mb-px transition-colors"
            style={{
              color: tab === key ? "var(--text-primary)" : "var(--text-muted)",
              borderBottom: `2px solid ${tab === key ? "var(--brand)" : "transparent"}`,
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "audit" ? <AuditTab /> : <SuggestionsTab />}
    </div>
  );
}
