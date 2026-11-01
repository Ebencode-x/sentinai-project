import { useState } from "react";
import { useNavigate } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { format } from "date-fns";
import { LogOut, Plus, Trash2 } from "lucide-react";
import { api, type AutonomySettings } from "@/api/client";
import { useAuth } from "@/hooks/useAuth";
import { useHealth } from "@/hooks/useHealth";
import { useTheme } from "@/hooks/useTheme";
import { useToast } from "@/components/Toast";
import { Card, CardHeader } from "@/components/Card";
import { SourcesTab } from "@/components/SourcesTab";

type Tab = "general" | "automation" | "sources" | "system";
type Severity = "warning" | "critical";

const TABS: { key: Tab; label: string }[] = [
  { key: "general", label: "General" },
  { key: "automation", label: "Automation" },
  { key: "sources", label: "Sources" },
  { key: "system", label: "System" },
];

const INPUT =
  "w-full rounded-md px-3 h-9 text-sm outline-hidden transition-colors " +
  "bg-(--bg-panel) border border-(--border) focus:border-(--brand) " +
  "text-(--text-primary) placeholder:text-(--text-muted)";

const BTN_GHOST =
  "inline-flex items-center gap-2 rounded-md px-3 h-8 text-sm font-medium transition-colors " +
  "border border-(--border-strong) text-(--text-secondary) " +
  "hover:text-(--text-primary) hover:bg-(--bg-hover) disabled:opacity-50";

/* Small building blocks */

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div
      className="flex items-center justify-between gap-4 px-4 py-3 text-sm"
      style={{ borderTop: "1px solid var(--border)" }}
    >
      <span style={{ color: "var(--text-secondary)" }}>{label}</span>
      <span className="font-medium text-right break-all">{children}</span>
    </div>
  );
}

function Switch({
  checked,
  onChange,
  disabled,
  label,
}: {
  checked: boolean;
  onChange: () => void;
  disabled?: boolean;
  label: string;
}) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={onChange}
      className="relative w-9 h-5 rounded-full shrink-0 transition-colors disabled:opacity-50"
      style={{ background: checked ? "var(--green)" : "var(--bg-hover)" }}
    >
      <span
        className="absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform"
        style={{ transform: checked ? "translateX(16px)" : undefined }}
      />
    </button>
  );
}

function AdminNote({ isAdmin }: { isAdmin: boolean }) {
  if (isAdmin) return null;
  return (
    <p className="px-4 pb-3 text-xs" style={{ color: "var(--text-muted)" }}>
      Only admins can change this. You are signed in as a viewer.
    </p>
  );
}

function ms(v: number | null | undefined): string {
  return v == null ? "n/a" : `${v.toFixed(1)} ms`;
}

/* Tab: General */

function GeneralTab() {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const { live, isBackendUp, ready } = useHealth();
  const navigate = useNavigate();

  const expiry = localStorage.getItem("sentinai_session_expiry");
  let expiresAt = "n/a";
  if (expiry) {
    try {
      expiresAt = format(new Date(expiry), "MMM d, yyyy HH:mm");
    } catch {
      expiresAt = "n/a";
    }
  }

  const connected = isBackendUp && ready?.status === "ok";
  const statusLabel = connected ? "Connected" : isBackendUp === null ? "Connecting" : "Unreachable";
  const statusColor = connected ? "var(--green)" : isBackendUp === null ? "var(--text-muted)" : "var(--red)";

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader title="Account" />
        <Row label="Email">{user?.email ?? "n/a"}</Row>
        <Row label="Role"><span className="capitalize">{user?.role ?? "n/a"}</span></Row>
        <Row label="Session expires">{expiresAt}</Row>
        <div className="px-4 py-3" style={{ borderTop: "1px solid var(--border)" }}>
          <button
            className={BTN_GHOST}
            onClick={() => {
              logout();
              navigate("/login");
            }}
          >
            <LogOut size={14} />
            Sign out
          </button>
        </div>
      </Card>

      <Card>
        <CardHeader title="Appearance" />
        <div className="flex items-center justify-between px-4 py-3 text-sm">
          <span style={{ color: "var(--text-secondary)" }}>Theme</span>
          <div
            className="flex rounded-md p-0.5"
            style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}
          >
            {(["dark", "light"] as const).map((t) => (
              <button
                key={t}
                onClick={() => theme !== t && toggle()}
                className="px-3 h-7 rounded text-xs font-medium capitalize transition-colors"
                style={{
                  background: theme === t ? "var(--bg-hover)" : "transparent",
                  color: theme === t ? "var(--text-primary)" : "var(--text-muted)",
                }}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader title="Backend" />
        <Row label="API address">{import.meta.env.VITE_API_URL || "Same origin"}</Row>
        <Row label="Service">{live?.service ?? "n/a"}</Row>
        <Row label="Status">
          <span className="inline-flex items-center gap-2">
            <span className="w-2 h-2 rounded-full" style={{ background: statusColor }} />
            {statusLabel}
          </span>
        </Row>
      </Card>
    </div>
  );
}

/* Tab: Automation */

function AutonomyCard({ isAdmin }: { isAdmin: boolean }) {
  const { toast } = useToast();
  const [saving, setSaving] = useState(false);
  const { data: autonomy, refetch } = useQuery({
    queryKey: ["autonomy"],
    queryFn: () => api.settings.getAutonomy().then((r) => r.data),
  });

  const options: { mode: AutonomySettings["mode"]; title: string; text: string }[] = [
    { mode: "propose_only", title: "Propose only", text: "SentinAI suggests a fix and waits for a person to act." },
    { mode: "auto_pr", title: "Auto-create PR", text: "SentinAI opens a GitHub pull request for each detected patch." },
  ];

  async function choose(mode: AutonomySettings["mode"]) {
    if (!isAdmin || saving || autonomy?.mode === mode) return;
    if (
      mode === "auto_pr" &&
      !window.confirm("SentinAI will open pull requests on its own. Make sure branch protection and required review are on. Continue?")
    ) {
      return;
    }
    setSaving(true);
    try {
      await api.settings.setAutonomy(mode);
      await refetch();
      toast("Autonomy mode updated", "ok");
    } catch {
      toast("Could not update autonomy mode", "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader title="Autonomy" />
      <p className="px-4 pt-3 text-sm" style={{ color: "var(--text-muted)" }}>
        Controls what SentinAI does once it has a proposed fix.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-4">
        {options.map((o) => {
          const active = autonomy?.mode === o.mode;
          return (
            <button
              key={o.mode}
              onClick={() => choose(o.mode)}
              disabled={!isAdmin || saving}
              className="text-left rounded-lg p-3 transition-colors disabled:cursor-not-allowed"
              style={{
                background: active ? "var(--brand-dim)" : "var(--bg-panel)",
                border: `1px solid ${active ? "var(--brand)" : "var(--border)"}`,
                opacity: !isAdmin && !active ? 0.6 : 1,
              }}
            >
              <p className="text-sm font-medium">{o.title}</p>
              <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>{o.text}</p>
            </button>
          );
        })}
      </div>
      {autonomy?.mode === "auto_pr" && (
        <p
          className="mx-4 mb-4 rounded-md px-3 py-2 text-xs"
          style={{ background: "var(--amber-dim)", color: "var(--amber)" }}
        >
          Auto-create PR is on. Branch protection and required review are strongly recommended.
        </p>
      )}
      <AdminNote isAdmin={isAdmin} />
    </Card>
  );
}

function ChannelsCard({ isAdmin }: { isAdmin: boolean }) {
  const { toast } = useToast();
  const { data: channels = [], refetch } = useQuery({
    queryKey: ["channels"],
    queryFn: () => api.settings.listChannels().then((r) => r.data),
  });

  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [type, setType] = useState<"slack" | "webhook">("slack");
  const [url, setUrl] = useState("");
  const [severities, setSeverities] = useState<Severity[]>(["critical"]);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  function toggleSeverity(s: Severity) {
    setSeverities((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]));
  }

  function resetForm() {
    setName("");
    setUrl("");
    setType("slack");
    setSeverities(["critical"]);
    setFormError(null);
    setShowForm(false);
  }

  async function create() {
    if (!name.trim()) return setFormError("Give the channel a name.");
    if (!/^https:\/\//i.test(url.trim())) return setFormError("The address must start with https://");
    if (severities.length === 0) return setFormError("Pick at least one severity.");
    setSaving(true);
    setFormError(null);
    try {
      await api.settings.createChannel({
        name: name.trim(),
        type,
        url: url.trim(),
        severities,
        enabled: true,
      });
      await refetch();
      resetForm();
      toast("Channel added", "ok");
    } catch {
      setFormError("Could not save the channel.");
    } finally {
      setSaving(false);
    }
  }

  async function toggle(id: string, enabled: boolean) {
    try {
      await api.settings.updateChannel(id, { enabled: !enabled });
      await refetch();
    } catch {
      toast("Could not update the channel", "error");
    }
  }

  async function remove(id: string, label: string) {
    if (!window.confirm(`Delete the channel "${label}"?`)) return;
    try {
      await api.settings.deleteChannel(id);
      await refetch();
      toast("Channel deleted", "ok");
    } catch {
      toast("Could not delete the channel", "error");
    }
  }

  return (
    <Card>
      <CardHeader title="Notification channels" />
      <p className="px-4 pt-3 text-sm" style={{ color: "var(--text-muted)" }}>
        Send incident alerts to Slack or a webhook, filtered by severity.
      </p>

      {channels.length === 0 ? (
        <p className="px-4 py-6 text-sm text-center" style={{ color: "var(--text-muted)" }}>
          No channels yet.
        </p>
      ) : (
        <ul className="mt-3">
          {channels.map((ch) => (
            <li
              key={ch.id}
              className="flex items-center gap-3 px-4 py-3"
              style={{ borderTop: "1px solid var(--border)", opacity: ch.enabled ? 1 : 0.6 }}
            >
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium truncate">{ch.name}</p>
                <p className="text-xs capitalize" style={{ color: "var(--text-muted)" }}>
                  {ch.type} · {ch.severities.join(", ")}
                </p>
              </div>
              <Switch
                checked={ch.enabled}
                onChange={() => toggle(ch.id, ch.enabled)}
                disabled={!isAdmin}
                label={`Enable ${ch.name}`}
              />
              <button
                onClick={() => remove(ch.id, ch.name)}
                disabled={!isAdmin}
                aria-label={`Delete ${ch.name}`}
                className="w-8 h-8 rounded-md flex items-center justify-center transition-colors disabled:opacity-40 hover:bg-(--red-dim) hover:text-(--red)"
                style={{ color: "var(--text-muted)" }}
              >
                <Trash2 size={15} />
              </button>
            </li>
          ))}
        </ul>
      )}

      {isAdmin && (
        <div className="p-4" style={{ borderTop: "1px solid var(--border)" }}>
          {!showForm ? (
            <button className={BTN_GHOST} onClick={() => setShowForm(true)}>
              <Plus size={14} />
              Add channel
            </button>
          ) : (
            <div className="flex flex-col gap-3">
              <input className={INPUT} value={name} onChange={(e) => setName(e.target.value)} placeholder="Channel name" />
              <select
                className={INPUT}
                value={type}
                onChange={(e) => setType(e.target.value as "slack" | "webhook")}
              >
                <option value="slack">Slack</option>
                <option value="webhook">Webhook</option>
              </select>
              <input
                className={INPUT}
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://hooks.slack.com/... or your endpoint"
              />
              <div className="flex gap-4">
                {(["warning", "critical"] as const).map((s) => (
                  <label key={s} className="inline-flex items-center gap-2 text-sm capitalize cursor-pointer">
                    <input
                      type="checkbox"
                      checked={severities.includes(s)}
                      onChange={() => toggleSeverity(s)}
                      className="accent-(--brand)"
                    />
                    {s}
                  </label>
                ))}
              </div>
              {formError && <p className="text-xs" style={{ color: "var(--red)" }}>{formError}</p>}
              <div className="flex gap-2">
                <button
                  onClick={create}
                  disabled={saving}
                  className="rounded-md px-3.5 h-9 text-sm font-medium transition-opacity disabled:opacity-60"
                  style={{ background: "var(--brand)", color: "#1a1a1a" }}
                >
                  {saving ? "Saving" : "Save channel"}
                </button>
                <button className={BTN_GHOST} onClick={resetForm}>Cancel</button>
              </div>
            </div>
          )}
        </div>
      )}
      <AdminNote isAdmin={isAdmin} />
    </Card>
  );
}

/* Tab: System */

function SystemTab() {
  const { ready } = useHealth();
  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: () => api.stats().then((r) => r.data),
    refetchInterval: 30_000,
  });

  const m = stats?.llm_metrics;
  const rate = m?.fallback_rate ?? stats?.fallback_rate;

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader title="Health checks" />
        {ready?.checks?.length ? (
          ready.checks.map((c, i) => {
            const color = c.status === "ok" ? "var(--green)" : c.status === "degraded" ? "var(--amber)" : "var(--red)";
            return (
              <div
                key={c.name}
                className="flex items-center gap-3 px-4 py-3 text-sm"
                style={{ borderTop: i === 0 ? undefined : "1px solid var(--border)" }}
              >
                <span className="w-2 h-2 rounded-full shrink-0" style={{ background: color }} />
                <span className="flex-1 min-w-0 truncate">{c.name}</span>
                <span className="text-xs capitalize" style={{ color }}>{c.status}</span>
                {c.latency_ms != null && (
                  <span className="text-xs w-16 text-right" style={{ color: "var(--text-muted)" }}>
                    {c.latency_ms.toFixed(1)} ms
                  </span>
                )}
              </div>
            );
          })
        ) : (
          <p className="p-6 text-sm text-center" style={{ color: "var(--text-muted)" }}>
            No readiness data yet.
          </p>
        )}
      </Card>

      <Card>
        <CardHeader title="Runtime" />
        <Row label="LLM provider">{stats?.llm_provider ?? "n/a"}</Row>
        <Row label="Scan runs">{stats?.total_scan_runs ?? "n/a"}</Row>
        <Row label="Events waiting">{stats?.events_pending ?? "n/a"}</Row>
        <Row label="Events failed">
          <span style={{ color: (stats?.events_failed ?? 0) > 0 ? "var(--red)" : undefined }}>
            {stats?.events_failed ?? "n/a"}
          </span>
        </Row>
        <Row label="Suggestions">{m?.total_suggestions ?? stats?.total_suggestions ?? "n/a"}</Row>
        <Row label="Fallback rate">
          <span style={{ color: rate != null && rate > 0.2 ? "var(--amber)" : undefined }}>
            {rate != null ? `${(rate * 100).toFixed(1)}%` : "n/a"}
          </span>
        </Row>
        <Row label="Average latency">{ms(m?.avg_latency_ms ?? stats?.avg_latency_ms)}</Row>
        <Row label="p95 latency">{ms(m?.p95_latency_ms ?? stats?.p95_latency_ms)}</Row>
      </Card>

      <Card>
        <CardHeader title="Configuration" />
        <Row label="Log file">{stats?.log_file_path ?? "n/a"}</Row>
        <Row label="Dedupe window">{stats?.dedupe_window_max ?? "n/a"}</Row>
        <Row label="Fingerprints tracked">{stats?.dedupe_fingerprints_tracked ?? "n/a"}</Row>
      </Card>
    </div>
  );
}

/* Page */

export default function Settings() {
  const { user } = useAuth();
  const [tab, setTab] = useState<Tab>("general");
  const isAdmin = user?.role === "admin";

  return (
    <div className="flex flex-col gap-4 max-w-3xl">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          Your account, automation rules and system status
        </p>
      </div>

      <div className="flex gap-1" style={{ borderBottom: "1px solid var(--border)" }}>
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className="px-3 py-2 text-sm font-medium -mb-px transition-colors"
            style={{
              color: tab === t.key ? "var(--text-primary)" : "var(--text-muted)",
              borderBottom: `2px solid ${tab === t.key ? "var(--brand)" : "transparent"}`,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "general" && <GeneralTab />}
      {tab === "automation" && (
        <div className="flex flex-col gap-4">
          <AutonomyCard isAdmin={isAdmin} />
          <ChannelsCard isAdmin={isAdmin} />
        </div>
      )}
      {tab === "sources" && <SourcesTab />}
      {tab === "system" && <SystemTab />}
    </div>
  );
}
