import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import { Check, Copy, Plus, RotateCw, Trash2 } from "lucide-react";
import { api, type IngestSource, type IngestSourceWithKey } from "@/api/client";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/components/Toast";
import { Card, CardHeader } from "@/components/Card";

const NAME_PATTERN = /^[a-z0-9][a-z0-9_-]{0,31}$/;
const QUIET_AFTER_MS = 60 * 60 * 1000;

const INPUT =
  "w-full rounded-md px-3 h-9 text-sm outline-hidden transition-colors " +
  "bg-(--bg-panel) border border-(--border) focus:border-(--brand) " +
  "text-(--text-primary) placeholder:text-(--text-muted)";

const BTN_GHOST =
  "inline-flex items-center gap-2 rounded-md px-3 h-8 text-sm font-medium transition-colors " +
  "border border-(--border-strong) text-(--text-secondary) " +
  "hover:text-(--text-primary) hover:bg-(--bg-hover) disabled:opacity-50";

const BTN_PRIMARY =
  "inline-flex items-center gap-2 rounded-md px-3.5 h-9 text-sm font-medium " +
  "transition-opacity disabled:opacity-60 disabled:cursor-not-allowed";

type Health = "live" | "quiet" | "waiting" | "revoked";

const HEALTH: Record<Health, { label: string; color: string }> = {
  live: { label: "Receiving", color: "var(--green)" },
  quiet: { label: "Quiet", color: "var(--amber)" },
  waiting: { label: "Waiting for first event", color: "var(--text-muted)" },
  revoked: { label: "Revoked", color: "var(--red)" },
};

function healthOf(source: IngestSource, now: number): Health {
  if (source.status === "revoked") return "revoked";
  if (!source.last_event_at) return "waiting";
  return now - new Date(source.last_event_at).getTime() > QUIET_AFTER_MS ? "quiet" : "live";
}

function ago(iso: string | null): string {
  return iso ? formatDistanceToNow(new Date(iso), { addSuffix: true }) : "never";
}

function errorText(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === "string" ? detail : fallback;
}

function StatusPill({ health }: { health: Health }) {
  const { label, color } = HEALTH[health];
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2 h-5 text-xs font-medium whitespace-nowrap"
      style={{ color, border: `1px solid color-mix(in srgb, ${color} 45%, transparent)` }}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
      {label}
    </span>
  );
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const [state, setState] = useState<"idle" | "done" | "failed">("idle");

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setState("done");
    } catch {
      setState("failed");
    }
    window.setTimeout(() => setState("idle"), 2000);
  }

  return (
    <button type="button" onClick={copy} className={BTN_GHOST} aria-label={`Copy ${label}`}>
      {state === "done" ? <Check size={14} /> : <Copy size={14} />}
      {state === "done" ? "Copied" : state === "failed" ? "Select it and copy by hand" : "Copy"}
    </button>
  );
}

function KeyPanel({ created, onDone }: { created: IngestSourceWithKey; onDone: () => void }) {
  const [saved, setSaved] = useState(false);
  const command = [
    `curl -X POST ${window.location.origin}/api/v1/events \\`,
    `  -H "Authorization: Bearer ${created.key}" \\`,
    `  -H "Content-Type: application/json" \\`,
    `  -d '{"events": [{"message": "KeyError: customer_id", "environment": "production"}]}'`,
  ].join("\n");

  return (
    <div
      className="m-4 rounded-md p-4 flex flex-col gap-3"
      style={{ border: "1px solid var(--amber)", background: "var(--bg-panel)" }}
    >
      <div>
        <p className="text-sm font-semibold">API key for {created.name}</p>
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          This is the only time the key is shown. SentinAI keeps a hash only, so a lost key has to
          be replaced.
        </p>
      </div>

      <div className="flex items-start gap-2">
        <code
          className="flex-1 min-w-0 break-all rounded-md px-3 py-2 text-xs font-mono select-all"
          style={{ background: "var(--bg-base)", border: "1px solid var(--border)" }}
        >
          {created.key}
        </code>
        <CopyButton text={created.key} label="key" />
      </div>

      <div>
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
            Send a first event
          </span>
          <CopyButton text={command} label="command" />
        </div>
        <pre
          className="rounded-md p-3 text-xs font-mono overflow-x-auto"
          style={{
            background: "var(--bg-base)",
            border: "1px solid var(--border)",
            color: "var(--text-secondary)",
          }}
        >
          {command}
        </pre>
      </div>

      <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
        <input type="checkbox" checked={saved} onChange={(e) => setSaved(e.target.checked)} />
        I have saved this key somewhere safe
      </label>

      <div>
        <button
          type="button"
          onClick={onDone}
          disabled={!saved}
          className={BTN_PRIMARY}
          style={{ background: "var(--brand)", color: "#1a1a1a" }}
        >
          Done
        </button>
      </div>
    </div>
  );
}

type Pending = { id: string; kind: "rotate" | "revoke" };

export function SourcesTab() {
  const { user } = useAuth();
  const { toast } = useToast();
  const isAdmin = user?.role === "admin";

  const {
    data: sources = [],
    refetch,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["sources"],
    queryFn: () => api.sources.list().then((r) => r.data),
    enabled: isAdmin,
    refetchInterval: 15_000,
  });

  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [created, setCreated] = useState<IngestSourceWithKey | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);
  const [busy, setBusy] = useState(false);
  const [rowError, setRowError] = useState<string | null>(null);

  async function create() {
    const value = name.trim();
    if (!NAME_PATTERN.test(value)) {
      return setFormError("Use lowercase letters, digits, - and _ (up to 32 characters).");
    }
    setCreating(true);
    setFormError(null);
    try {
      const res = await api.sources.create(value);
      setCreated(res.data);
      setName("");
      await refetch();
    } catch (err) {
      setFormError(errorText(err, "Could not create the source."));
    } finally {
      setCreating(false);
    }
  }

  async function confirm() {
    if (!pending) return;
    setBusy(true);
    setRowError(null);
    try {
      if (pending.kind === "rotate") {
        const res = await api.sources.rotate(pending.id);
        setCreated(res.data);
      } else {
        await api.sources.revoke(pending.id);
        toast("Source revoked", "ok");
      }
      setPending(null);
      await refetch();
    } catch (err) {
      setRowError(errorText(err, "That did not work. Try again."));
    } finally {
      setBusy(false);
    }
  }

  if (!isAdmin) {
    return (
      <Card>
        <CardHeader title="Sources" />
        <p className="p-6 text-sm text-center" style={{ color: "var(--text-muted)" }}>
          Only admins can see and manage the services that send events.
        </p>
      </Card>
    );
  }

  const now = Date.now();
  const activeCount = sources.filter((s) => s.status === "active").length;

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader
          title="Sources"
          action={
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>
              {activeCount} active
            </span>
          }
        />
        <p className="px-4 pt-3 text-sm" style={{ color: "var(--text-secondary)" }}>
          A source is a service that sends errors to SentinAI. Each one has its own key, so you can
          rotate or revoke it without touching the others.
        </p>
        <p className="px-4 pt-1 pb-3 text-xs font-mono" style={{ color: "var(--text-muted)" }}>
          POST /api/v1/events with Authorization: Bearer your-key
        </p>

        {created && <KeyPanel created={created} onDone={() => setCreated(null)} />}

        <div className="flex flex-wrap items-start gap-2 px-4 pb-4">
          <div className="flex flex-col gap-1 flex-1 min-w-48">
            <input
              className={INPUT}
              value={name}
              maxLength={32}
              placeholder="Service name, for example agrolink"
              aria-label="Source name"
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void create();
              }}
            />
            {formError && (
              <p className="text-xs" style={{ color: "var(--red)" }}>
                {formError}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={create}
            disabled={creating || name.trim() === ""}
            className={BTN_PRIMARY}
            style={{ background: "var(--brand)", color: "#1a1a1a" }}
          >
            <Plus size={14} />
            {creating ? "Creating" : "Create source"}
          </button>
        </div>
      </Card>

      <Card>
        <CardHeader title="Connected services" />
        {isLoading ? (
          <p className="p-6 text-sm text-center" style={{ color: "var(--text-muted)" }}>
            Loading sources
          </p>
        ) : isError ? (
          <p className="p-6 text-sm text-center" style={{ color: "var(--red)" }}>
            Could not load sources.
          </p>
        ) : sources.length === 0 ? (
          <div className="px-4 py-6">
            <p className="text-sm font-medium mb-3">No sources yet</p>
            <ol className="flex flex-col gap-2 text-sm" style={{ color: "var(--text-secondary)" }}>
              {[
                "Create a source above and name it after your service.",
                "Copy the key. It is shown once.",
                "Send your first event. It appears here and on the dashboard within seconds.",
              ].map((step, i) => (
                <li key={step} className="flex gap-3">
                  <span className="font-mono text-xs pt-0.5" style={{ color: "var(--text-muted)" }}>
                    0{i + 1}
                  </span>
                  {step}
                </li>
              ))}
            </ol>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr
                  className="text-left text-xs"
                  style={{ color: "var(--text-muted)", background: "var(--bg-panel)" }}
                >
                  <th className="px-4 py-2 font-medium">Source</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">Last event</th>
                  <th className="px-4 py-2 font-medium">Key</th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody>
                {sources.map((s) => {
                  const health = healthOf(s, now);
                  const asking = pending !== null && pending.id === s.id ? pending.kind : null;
                  return (
                    <tr key={s.id} style={{ borderTop: "1px solid var(--border)" }}>
                      <td className="px-4 py-3">
                        <div className="font-medium">{s.name}</div>
                        <div className="text-xs" style={{ color: "var(--text-muted)" }}>
                          Created {ago(s.created_at)}
                          {s.created_by ? ` by ${s.created_by}` : ""}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <StatusPill health={health} />
                      </td>
                      <td
                        className="px-4 py-3 whitespace-nowrap"
                        style={{ color: "var(--text-secondary)" }}
                      >
                        {s.last_event_at ? ago(s.last_event_at) : "No events yet"}
                      </td>
                      <td className="px-4 py-3">
                        <code className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>
                          {s.key_prefix}_...
                        </code>
                      </td>
                      <td className="px-4 py-3 text-right whitespace-nowrap">
                        {s.status === "revoked" ? (
                          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                            Revoked {ago(s.revoked_at)}
                          </span>
                        ) : asking ? (
                          <div className="inline-flex items-center gap-2">
                            <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
                              {asking === "rotate"
                                ? "Replace the key? The old one stops working now."
                                : "Revoke this source?"}
                            </span>
                            <button
                              type="button"
                              className={BTN_GHOST}
                              disabled={busy}
                              onClick={() => setPending(null)}
                            >
                              Cancel
                            </button>
                            <button
                              type="button"
                              disabled={busy}
                              onClick={confirm}
                              className="inline-flex items-center rounded-md px-3 h-8 text-sm font-medium transition-opacity disabled:opacity-60"
                              style={{
                                background: asking === "revoke" ? "var(--red)" : "var(--brand)",
                                color: asking === "revoke" ? "#ffffff" : "#1a1a1a",
                              }}
                            >
                              {busy ? "Working" : asking === "rotate" ? "Rotate" : "Revoke"}
                            </button>
                          </div>
                        ) : (
                          <div className="inline-flex items-center gap-2">
                            <button
                              type="button"
                              className={BTN_GHOST}
                              onClick={() => {
                                setRowError(null);
                                setPending({ id: s.id, kind: "rotate" });
                              }}
                            >
                              <RotateCw size={14} />
                              Rotate key
                            </button>
                            <button
                              type="button"
                              className={`${BTN_GHOST} hover:text-(--red)`}
                              onClick={() => {
                                setRowError(null);
                                setPending({ id: s.id, kind: "revoke" });
                              }}
                            >
                              <Trash2 size={14} />
                              Revoke
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {rowError && (
          <p className="px-4 py-3 text-xs" style={{ color: "var(--red)" }}>
            {rowError}
          </p>
        )}
      </Card>
    </div>
  );
}
