import { useState, useEffect } from "react";
import { useApiKey } from "@/hooks/useApiKey";
import { useHealth } from "@/hooks/useHealth";
import { useTheme } from "@/hooks/useTheme";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import {
  Terminal, Shield, Activity, Server, Trash2,
  RefreshCw, Eye, EyeOff, CheckCircle, XCircle,
  Cpu, HardDrive, Zap, GitPullRequest, Bell, Plus, X,
} from "lucide-react";

/* ── tiny section wrapper ─────────────────────────────────────────────── */
function Section({ title, icon: Icon, children }: {
  title: string; icon: React.ElementType; children: React.ReactNode;
}) {
  return (
    <div style={{ border: "0.5px solid var(--border)", borderRadius: "8px", overflow: "hidden" }}>
      <div style={{
        padding: "10px 16px", display: "flex", alignItems: "center", gap: "8px",
        borderBottom: "0.5px solid var(--border)", background: "var(--bg-elevated)",
      }}>
        <Icon size={13} style={{ color: "var(--text-muted)" }} strokeWidth={1.75} />
        <span style={{
          fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
          letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--text-muted)",
        }}>{title}</span>
      </div>
      <div style={{ padding: "16px", background: "var(--bg-surface)" }}>{children}</div>
    </div>
  );
}

/* ── key-value row ────────────────────────────────────────────────────── */
function KV({ label, value, mono = true, accent }: {
  label: string; value: string | React.ReactNode; mono?: boolean; accent?: string;
}) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center",
      padding: "7px 0", borderBottom: "0.5px solid var(--border)" }}>
      <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
        color: "var(--text-muted)", letterSpacing: "0.06em" }}>{label}</span>
      <span style={{
        fontFamily: mono ? "'IBM Plex Mono', monospace" : "'DM Sans', sans-serif",
        fontSize: "11px", color: accent ?? "var(--text-secondary)",
      }}>{value}</span>
    </div>
  );
}

/* ── check row ────────────────────────────────────────────────────────── */
function CheckRow({ name, status, latency }: { name: string; status: string; latency?: number }) {
  const ok  = status === "ok";
  const deg = status === "degraded";
  const color = ok ? "var(--green)" : deg ? "var(--amber)" : "var(--red)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "10px",
      padding: "7px 0", borderBottom: "0.5px solid var(--border)" }}>
      {ok
        ? <CheckCircle size={12} style={{ color: "var(--green)", flexShrink: 0 }} strokeWidth={2} />
        : <XCircle    size={12} style={{ color,               flexShrink: 0 }} strokeWidth={2} />}
      <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
        color: "var(--text-secondary)", flex: 1 }}>{name}</span>
      <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "9px", color }}>
        {status.toUpperCase()}
      </span>
      {latency != null && (
        <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "9px",
          color: "var(--text-muted)" }}>{latency.toFixed(1)}ms</span>
      )}
    </div>
  );
}

/* ── main ─────────────────────────────────────────────────────────────── */
export default function Settings() {
  const { clearKey }      = useApiKey();
  const { ready, live, isBackendUp } = useHealth();
  const { theme, toggle } = useTheme();
  const navigate          = useNavigate();

  /* api key field */
  const storedKey = localStorage.getItem("sentinai_api_key") ?? "";
  const expiry    = localStorage.getItem("sentinai_key_expiry");
  const expiresAt = expiry ? new Date(parseInt(expiry, 10)).toLocaleString() : "—";

  const [keyVisible, setKeyVisible] = useState(false);
  const [apiUrl, setApiUrl]         = useState(
    localStorage.getItem("sentinai_api_url") ?? (import.meta.env.VITE_API_URL ?? "/api")
  );
  const [urlSaved, setUrlSaved]     = useState(false);

  /* stats */
  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn:  () => api.stats().then((r) => r.data),
    refetchInterval: 30_000,
  });

  const { data: autonomy, refetch: refetchAutonomy } = useQuery({
    queryKey: ["autonomy"],
    queryFn: () => api.settings.getAutonomy().then((r) => r.data),
  });
  const [autonomySaving, setAutonomySaving] = useState(false);

  async function setAutonomyMode(mode: "propose_only" | "auto_pr") {
    if (autonomy?.mode === mode || autonomySaving) return;
    setAutonomySaving(true);
    try {
      await api.settings.setAutonomy(mode);
      await refetchAutonomy();
    } finally {
      setAutonomySaving(false);
    }
  }

  const { data: channels, refetch: refetchChannels } = useQuery({
    queryKey: ["channels"],
    queryFn: () => api.settings.listChannels().then((r) => r.data),
  });
  const [showChannelForm, setShowChannelForm] = useState(false);
  const [channelName, setChannelName] = useState("");
  const [channelType, setChannelType] = useState<"slack" | "webhook">("slack");
  const [channelUrl, setChannelUrl] = useState("");
  const [channelSeverities, setChannelSeverities] = useState<Array<"warning" | "critical">>(["critical"]);
  const [channelSaving, setChannelSaving] = useState(false);

  function toggleSeverity(sev: "warning" | "critical") {
    setChannelSeverities((prev) =>
      prev.includes(sev) ? prev.filter((s) => s !== sev) : [...prev, sev]
    );
  }

  async function createChannel() {
    if (!channelName.trim() || !channelUrl.trim() || channelSeverities.length === 0) return;
    setChannelSaving(true);
    try {
      await api.settings.createChannel({
        name: channelName.trim(),
        type: channelType,
        url: channelUrl.trim(),
        severities: channelSeverities,
        enabled: true,
      });
      setChannelName("");
      setChannelUrl("");
      setChannelSeverities(["critical"]);
      setShowChannelForm(false);
      await refetchChannels();
    } finally {
      setChannelSaving(false);
    }
  }

  async function toggleChannelEnabled(id: string, enabled: boolean) {
    await api.settings.updateChannel(id, { enabled: !enabled });
    await refetchChannels();
  }

  async function deleteChannel(id: string) {
    await api.settings.deleteChannel(id);
    await refetchChannels();
  }

  /* uptime */
  const [uptime, setUptime] = useState(0);
  useEffect(() => {
    const start = Date.now();
    const id = setInterval(() => setUptime(Math.floor((Date.now() - start) / 1000)), 1000);
    return () => clearInterval(id);
  }, []);
  const fmtUptime = (s: number) => {
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
    return [h, m, sec].map((v) => String(v).padStart(2, "0")).join(":");
  };

  function saveUrl() {
    localStorage.setItem("sentinai_api_url", apiUrl.trim());
    setUrlSaved(true);
    setTimeout(() => setUrlSaved(false), 2000);
  }

  function handleSignOut() {
    clearKey();
    navigate("/");
  }

  const maskedKey = storedKey
    ? storedKey.slice(0, 8) + "•".repeat(Math.max(0, storedKey.length - 12)) + storedKey.slice(-4)
    : "—";

  const overallOk = isBackendUp && ready?.status === "ok";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "12px",
      maxWidth: "720px", animation: "slideUp 0.3s ease-out both" }}>

      {/* page header */}
      <div style={{ marginBottom: "4px" }}>
        <h1 style={{ fontFamily: "'Syne', sans-serif", fontSize: "13px",
          fontWeight: 700, letterSpacing: "0.14em", textTransform: "uppercase",
          color: "var(--text-primary)" }}>Settings</h1>
        <p style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
          color: "var(--text-muted)", marginTop: "4px", letterSpacing: "0.04em" }}>
          operator console · runtime configuration
        </p>
      </div>

      {/* ── Authentication ───────────────────────────────────────────── */}
      <Section title="Authentication" icon={Shield}>
        <KV label="KEY" value={
          <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "11px",
              color: "var(--text-secondary)" }}>
              {keyVisible ? storedKey || "—" : maskedKey}
            </span>
            <button onClick={() => setKeyVisible((v) => !v)}
              style={{ background: "none", border: "none", cursor: "pointer",
                color: "var(--text-muted)", padding: 0, display: "flex" }}>
              {keyVisible
                ? <EyeOff size={11} strokeWidth={1.75} />
                : <Eye    size={11} strokeWidth={1.75} />}
            </button>
          </span>
        } />
        <KV label="EXPIRES" value={expiresAt} />
        <KV label="TTL" value="8h from login" />
        <div style={{ marginTop: "12px" }}>
          <button onClick={handleSignOut} style={{
            display: "flex", alignItems: "center", gap: "6px",
            fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
            letterSpacing: "0.08em", padding: "7px 14px",
            border: "0.5px solid var(--border-strong)", borderRadius: "6px",
            background: "var(--bg-elevated)", color: "var(--text-secondary)",
            cursor: "pointer", transition: "all 0.15s",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = "var(--red)";
            e.currentTarget.style.color = "var(--red)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = "var(--border-strong)";
            e.currentTarget.style.color = "var(--text-secondary)";
          }}>
            <Trash2 size={11} strokeWidth={1.75} />
            clear session
          </button>
        </div>
      </Section>

      {/* ── Backend connection ───────────────────────────────────────── */}
      <Section title="Backend" icon={Server}>
        <KV label="URL" value={import.meta.env.VITE_API_URL ?? "/api"} />
        <KV label="SERVICE" value={live?.service ?? "—"} />
        <KV label="STATUS" value={
          <span style={{ color: overallOk ? "var(--green)" : "var(--red)",
            fontFamily: "'IBM Plex Mono', monospace", fontSize: "11px" }}>
            {overallOk ? "CONNECTED" : isBackendUp === null ? "CONNECTING" : "UNREACHABLE"}
          </span>
        } />
        <div style={{ marginTop: "12px", display: "flex", flexDirection: "column", gap: "6px" }}>
          <label style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
            color: "var(--text-muted)", letterSpacing: "0.06em" }}>
            OVERRIDE URL (session only)
          </label>
          <div style={{ display: "flex", gap: "8px" }}>
            <input value={apiUrl} onChange={(e) => setApiUrl(e.target.value)}
              style={{ flex: 1, background: "var(--bg-base)", border: "0.5px solid var(--border-strong)",
                borderRadius: "6px", padding: "7px 10px", color: "var(--text-primary)",
                fontFamily: "'IBM Plex Mono', monospace", fontSize: "11px", outline: "none" }}
              onFocus={(e) => { e.currentTarget.style.borderColor = "var(--cyan)"; }}
              onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border-strong)"; }}
              placeholder="https://your-backend.com" />
            <button onClick={saveUrl} style={{
              padding: "7px 14px", borderRadius: "6px",
              border: urlSaved ? "0.5px solid var(--green)" : "0.5px solid var(--border-strong)",
              background: urlSaved ? "var(--green-dim)" : "var(--bg-elevated)",
              color: urlSaved ? "var(--green)" : "var(--text-secondary)",
              fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
              cursor: "pointer", transition: "all 0.2s",
            }}>
              {urlSaved ? "saved" : "save"}
            </button>
          </div>
        </div>
      </Section>

      {/* ── Autonomy ─────────────────────────────────────────────────── */}
      <Section title="Autonomy" icon={GitPullRequest}>
        <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "12px",
          color: "var(--text-muted)", marginBottom: "12px", lineHeight: 1.6 }}>
          Controls what SentinAI does once it has a proposed fix.
        </p>
        <div style={{ display: "flex", gap: "8px" }}>
          {([
            { mode: "propose_only" as const, label: "Propose only" },
            { mode: "auto_pr" as const, label: "Auto-create PR" },
          ]).map(({ mode, label }) => {
            const active = autonomy?.mode === mode;
            return (
              <button key={mode} onClick={() => setAutonomyMode(mode)} disabled={autonomySaving}
                style={{
                  flex: 1, fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
                  letterSpacing: "0.06em", padding: "9px 12px", borderRadius: "6px",
                  border: active ? "0.5px solid var(--cyan)" : "0.5px solid var(--border-strong)",
                  background: active ? "var(--bg-base)" : "var(--bg-elevated)",
                  color: active ? "var(--cyan)" : "var(--text-secondary)",
                  cursor: autonomySaving ? "wait" : "pointer", transition: "all 0.15s",
                }}>
                {label}
              </button>
            );
          })}
        </div>
        {autonomy?.mode === "auto_pr" && (
          <p style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "9.5px",
            color: "var(--amber)", lineHeight: 1.5, marginTop: "10px" }}>
            ⚠ SentinAI will open GitHub PRs automatically for detected patches. Branch protection + required review strongly recommended.
          </p>
        )}
      </Section>

      {/* ── Notification Channels ───────────────────────────────────── */}
      <Section title="Notification Channels" icon={Bell}>
        <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "12px",
          color: "var(--text-muted)", marginBottom: "12px", lineHeight: 1.6 }}>
          Route incident alerts to Slack or a webhook, filtered by severity.
        </p>

        {channels && channels.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: "6px", marginBottom: "12px" }}>
            {channels.map((ch) => (
              <div key={ch.id} style={{
                display: "flex", alignItems: "center", gap: "10px",
                padding: "8px 10px", borderRadius: "6px",
                border: "0.5px solid var(--border)", background: "var(--bg-elevated)",
                opacity: ch.enabled ? 1 : 0.5,
              }}>
                <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
                  color: "var(--text-secondary)", flex: 1 }}>
                  {ch.name} <span style={{ color: "var(--text-muted)" }}>· {ch.type}</span>
                </span>
                <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "9px",
                  color: "var(--text-muted)" }}>
                  {ch.severities.join(", ")}
                </span>
                <button onClick={() => toggleChannelEnabled(ch.id, ch.enabled)} style={{
                  fontFamily: "'IBM Plex Mono', monospace", fontSize: "9px",
                  padding: "3px 8px", borderRadius: "4px", cursor: "pointer",
                  border: `0.5px solid ${ch.enabled ? "var(--green)" : "var(--border-strong)"}`,
                  background: "transparent",
                  color: ch.enabled ? "var(--green)" : "var(--text-muted)",
                }}>
                  {ch.enabled ? "ON" : "OFF"}
                </button>
                <button onClick={() => deleteChannel(ch.id)} style={{
                  background: "none", border: "none", cursor: "pointer",
                  color: "var(--text-muted)", padding: "3px", display: "flex",
                }}>
                  <X size={12} strokeWidth={1.75} />
                </button>
              </div>
            ))}
          </div>
        )}

        {!showChannelForm ? (
          <button onClick={() => setShowChannelForm(true)} style={{
            display: "flex", alignItems: "center", gap: "6px",
            fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
            letterSpacing: "0.06em", padding: "7px 14px",
            border: "0.5px solid var(--border-strong)", borderRadius: "6px",
            background: "var(--bg-elevated)", color: "var(--text-secondary)",
            cursor: "pointer",
          }}>
            <Plus size={11} strokeWidth={1.75} />
            add channel
          </button>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            <input value={channelName} onChange={(e) => setChannelName(e.target.value)}
              placeholder="Channel name" style={{
                background: "var(--bg-base)", border: "0.5px solid var(--border-strong)",
                borderRadius: "6px", padding: "7px 10px", color: "var(--text-primary)",
                fontFamily: "'IBM Plex Mono', monospace", fontSize: "11px", outline: "none",
              }} />
            <div style={{ display: "flex", gap: "8px" }}>
              <select value={channelType} onChange={(e) => setChannelType(e.target.value as "slack" | "webhook")}
                style={{
                  flex: 1, background: "var(--bg-base)", border: "0.5px solid var(--border-strong)",
                  borderRadius: "6px", padding: "7px 10px", color: "var(--text-primary)",
                  fontFamily: "'IBM Plex Mono', monospace", fontSize: "11px",
                }}>
                <option value="slack">Slack</option>
                <option value="webhook">Webhook</option>
              </select>
            </div>
            <input value={channelUrl} onChange={(e) => setChannelUrl(e.target.value)}
              placeholder="https://hooks.slack.com/... or https://your-endpoint.com" style={{
                background: "var(--bg-base)", border: "0.5px solid var(--border-strong)",
                borderRadius: "6px", padding: "7px 10px", color: "var(--text-primary)",
                fontFamily: "'IBM Plex Mono', monospace", fontSize: "11px", outline: "none",
              }} />
            <div style={{ display: "flex", gap: "12px" }}>
              {(["warning", "critical"] as const).map((sev) => (
                <label key={sev} style={{
                  display: "flex", alignItems: "center", gap: "6px", cursor: "pointer",
                  fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
                  color: "var(--text-secondary)",
                }}>
                  <input type="checkbox" checked={channelSeverities.includes(sev)}
                    onChange={() => toggleSeverity(sev)} />
                  {sev}
                </label>
              ))}
            </div>
            <div style={{ display: "flex", gap: "8px" }}>
              <button onClick={createChannel} disabled={channelSaving} style={{
                flex: 1, fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
                padding: "7px 14px", borderRadius: "6px",
                border: "0.5px solid var(--cyan)", background: "var(--bg-base)",
                color: "var(--cyan)", cursor: channelSaving ? "wait" : "pointer",
              }}>
                {channelSaving ? "saving…" : "save channel"}
              </button>
              <button onClick={() => setShowChannelForm(false)} style={{
                fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
                padding: "7px 14px", borderRadius: "6px",
                border: "0.5px solid var(--border-strong)", background: "var(--bg-elevated)",
                color: "var(--text-secondary)", cursor: "pointer",
              }}>
                cancel
              </button>
            </div>
          </div>
        )}
      </Section>

      {/* ── System diagnostics ───────────────────────────────────────── */}
      <Section title="Diagnostics" icon={Activity}>
        {ready?.checks?.length
          ? ready.checks.map((c) => (
              <CheckRow key={c.name} name={c.name} status={c.status} latency={c.latency_ms} />
            ))
          : <p style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
              color: "var(--text-muted)" }}>no readiness data</p>}
      </Section>

      {/* ── Runtime metrics ──────────────────────────────────────────── */}
      <Section title="Runtime" icon={Cpu}>
        <KV label="SCAN RUNS"     value={String(stats?.total_scan_runs ?? "—")} />
        <KV label="SUGGESTIONS"   value={String(stats?.total_suggestions ?? "—")} />
        <KV label="FALLBACK RATE" value={
          stats?.fallback_rate != null ? `${(stats.fallback_rate * 100).toFixed(1)}%` : "—"
        } accent={
          stats?.fallback_rate != null && stats.fallback_rate > 0.2
            ? "var(--amber)" : undefined
        } />
        <KV label="AVG LATENCY"   value={
          stats?.avg_latency_ms != null ? `${stats.avg_latency_ms.toFixed(1)}ms` : "—"
        } />
        <KV label="P95 LATENCY"   value={
          stats?.p95_latency_ms != null ? `${stats.p95_latency_ms.toFixed(1)}ms` : "—"
        } />
        <KV label="SESSION UPTIME" value={fmtUptime(uptime)} />
      </Section>

      {/* ── Appearance ───────────────────────────────────────────────── */}
      <Section title="Appearance" icon={Zap}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "7px 0" }}>
          <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
            color: "var(--text-muted)", letterSpacing: "0.06em" }}>THEME</span>
          <button onClick={toggle} style={{
            display: "flex", alignItems: "center", gap: "8px",
            fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
            letterSpacing: "0.08em", padding: "6px 14px",
            border: "0.5px solid var(--border-strong)", borderRadius: "6px",
            background: "var(--bg-elevated)", color: "var(--text-secondary)",
            cursor: "pointer", transition: "all 0.15s", textTransform: "uppercase",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = "var(--cyan)";
            e.currentTarget.style.color = "var(--cyan)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = "var(--border-strong)";
            e.currentTarget.style.color = "var(--text-secondary)";
          }}>
            <RefreshCw size={10} strokeWidth={2} />
            {theme === "dark" ? "dark" : "light"}
          </button>
        </div>
        <KV label="FONT STACK" value="Syne · DM Sans · IBM Plex Mono" mono={false} />
        <KV label="VERSION"    value="v0.1.0" />
      </Section>

      {/* ── Build info ───────────────────────────────────────────────── */}
      <Section title="Build" icon={HardDrive}>
        <KV label="RELEASE"    value="v0.1.0" />
        <KV label="COMMIT"     value="1125be6" />
        <KV label="PROVIDER"   value={stats ? "claude" : "—"} />
        <KV label="LOG PATH"   value={stats?.log_file_path ?? "—"} />
        <KV label="DEDUPE WIN" value={stats?.dedupe_window_max != null ? `${stats.dedupe_window_max}` : "—"} />
      </Section>

      {/* ── Danger zone ──────────────────────────────────────────────── */}
      <Section title="Danger Zone" icon={Terminal}>
        <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "12px",
          color: "var(--text-muted)", marginBottom: "12px", lineHeight: 1.6 }}>
          Destructive operations. No confirmation dialogs.
        </p>
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          {[
            { label: "sign out + clear session", action: handleSignOut, color: "var(--red)" },
          ].map(({ label, action, color }) => (
            <button key={label} onClick={action} style={{
              fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
              letterSpacing: "0.08em", padding: "7px 14px",
              border: `0.5px solid ${color}`, borderRadius: "6px",
              background: "transparent", color,
              cursor: "pointer", transition: "all 0.15s",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "var(--red-dim)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}>
              {label}
            </button>
          ))}
        </div>
      </Section>

    </div>
  );
}
