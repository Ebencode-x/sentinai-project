import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type Suggestion } from "@/api/client";
import { format, parseISO } from "date-fns";
import EmptyState from "@/components/EmptyState";
import ErrorBanner from "@/components/ErrorBanner";
import { Search, X } from "lucide-react";

export default function AuditExplorer() {
  const [q, setQ] = useState("");

  const { data: suggestions = [], isLoading, error } = useQuery({
    queryKey: ["suggestions"],
    queryFn: () => api.suggestions().then((r) => r.data),
    refetchInterval: 30_000,
  });

  const filtered = useMemo(() => {
    if (!q.trim()) return suggestions;
    const lower = q.toLowerCase();
    return suggestions.filter(
      (s) =>
        s.rule.toLowerCase().includes(lower) ||
        s.explanation.toLowerCase().includes(lower) ||
        s.patch_id.toLowerCase().includes(lower)
    );
  }, [suggestions, q]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px",
      animation: "slideUp 0.3s ease-out both" }}>

      <div>
        <h1 style={{ fontFamily: "'Syne', sans-serif", fontSize: "13px", fontWeight: 700,
          letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--text-primary)" }}>
          Audit Explorer
        </h1>
        <p style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
          color: "var(--text-muted)", marginTop: "4px" }}>
          searchable remediation record
        </p>
      </div>

      {/* Search */}
      <div style={{ position: "relative" }}>
        <Search size={12} strokeWidth={1.75} style={{ position: "absolute", left: "12px",
          top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
        <input value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="rule · explanation · patch_id"
          style={{ width: "100%", background: "var(--bg-surface)",
            border: "0.5px solid var(--border-strong)", borderRadius: "6px",
            padding: "9px 36px", color: "var(--text-primary)",
            fontFamily: "'IBM Plex Mono', monospace", fontSize: "11px", outline: "none",
            boxSizing: "border-box" }}
          onFocus={(e) => { e.currentTarget.style.borderColor = "var(--cyan)"; }}
          onBlur={(e)  => { e.currentTarget.style.borderColor = "var(--border-strong)"; }} />
        {q && (
          <button onClick={() => setQ("")} style={{ position: "absolute", right: "12px",
            top: "50%", transform: "translateY(-50%)", background: "none", border: "none",
            cursor: "pointer", color: "var(--text-muted)", display: "flex" }}>
            <X size={12} strokeWidth={2} />
          </button>
        )}
      </div>

      <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
        color: "var(--text-muted)" }}>
        {filtered.length} of {suggestions.length} records
      </div>

      {error && <ErrorBanner message="Failed to load suggestions." />}

      {isLoading ? (
        <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
          color: "var(--text-muted)" }}>loading…</div>
      ) : filtered.length === 0 ? (
        <EmptyState message="no records found" />
      ) : (
        <div style={{ border: "0.5px solid var(--border)", borderRadius: "6px",
          overflow: "hidden" }}>
          {/* Header row */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr 90px 80px",
            gap: "12px", padding: "8px 16px",
            background: "var(--bg-elevated)", borderBottom: "0.5px solid var(--border)",
            fontFamily: "'IBM Plex Mono', monospace", fontSize: "9px",
            letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--text-muted)" }}>
            <span>patch id</span>
            <span>rule · explanation</span>
            <span>confidence</span>
            <span style={{ textAlign: "right" }}>time</span>
          </div>
          {filtered.map((s, i) => (
            <AuditRow key={s.patch_id} suggestion={s} index={i} total={filtered.length} />
          ))}
        </div>
      )}
    </div>
  );
}

function AuditRow({ suggestion: s, index, total }: {
  suggestion: Suggestion; index: number; total: number;
}) {
  const [open, setOpen] = useState(false);
  const pct = Math.round(s.confidence * 100);

  const ts = (() => {
    try { return s.created_at ? format(parseISO(s.created_at), "MMM dd HH:mm") : "—"; }
    catch { return "—"; }
  })();

  const confColor = pct >= 80 ? "var(--green)" : pct >= 50 ? "var(--amber)" : "var(--red)";

  return (
    <>
      <div onClick={() => setOpen((o) => !o)} style={{
        display: "grid", gridTemplateColumns: "1fr 2fr 90px 80px",
        gap: "12px", padding: "10px 16px", cursor: "pointer", transition: "background 0.12s",
        borderBottom: index === total - 1 ? "none" : "0.5px solid var(--border)",
        background: open ? "var(--bg-elevated)" : "var(--bg-surface)",
      }}
      onMouseEnter={(e) => { if (!open) e.currentTarget.style.background = "var(--bg-elevated)"; }}
      onMouseLeave={(e) => { if (!open) e.currentTarget.style.background = "var(--bg-surface)"; }}>
        <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
          color: "var(--cyan)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
          title={s.patch_id}>
          {s.patch_id.slice(0, 12)}…
        </span>
        <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "12px",
          color: "var(--text-primary)", overflow: "hidden", textOverflow: "ellipsis",
          whiteSpace: "nowrap" }} title={s.explanation}>
          <span style={{ color: "var(--text-muted)" }}>{s.rule}</span>
          {" · "}{s.explanation.slice(0, 55)}{s.explanation.length > 55 ? "…" : ""}
        </span>
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <div style={{ flex: 1, height: "3px", background: "var(--border)",
            borderRadius: "2px", overflow: "hidden" }}>
            <div style={{ height: "100%", width: `${pct}%`,
              background: confColor, borderRadius: "2px", transition: "width 0.3s" }} />
          </div>
          <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
            color: confColor, width: "28px", textAlign: "right" }}>{pct}%</span>
        </div>
        <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
          color: "var(--text-muted)", textAlign: "right" }}>{ts}</span>
      </div>

      {open && (
        <div style={{ padding: "12px 16px", background: "var(--bg-base)",
          borderBottom: index === total - 1 ? "none" : "0.5px solid var(--border)",
          animation: "fadeIn 0.18s ease-out both" }}>
          <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "9px",
            letterSpacing: "0.1em", color: "var(--text-muted)", marginBottom: "6px" }}>
            full explanation
          </div>
          <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "12px",
            color: "var(--text-secondary)", lineHeight: 1.6 }}>{s.explanation}</p>
          <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "9px",
            color: "var(--text-muted)", marginTop: "8px" }}>
            patch_id: {s.patch_id}
          </div>
        </div>
      )}
    </>
  );
}
