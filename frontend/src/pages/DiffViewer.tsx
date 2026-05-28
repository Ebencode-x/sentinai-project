import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import EmptyState from "@/components/EmptyState";
import ErrorBanner from "@/components/ErrorBanner";
import { FileCode, ChevronRight } from "lucide-react";

function renderDiff(raw: string) {
  return raw.split("\n").map((line, i) => {
    const isAdd    = line.startsWith("+") && !line.startsWith("+++");
    const isRemove = line.startsWith("-") && !line.startsWith("---");
    const isHunk   = line.startsWith("@@");
    const isMeta   = line.startsWith("---") || line.startsWith("+++");

    const bg = isAdd ? "rgba(34,201,123,0.06)" : isRemove ? "rgba(255,77,106,0.06)"
      : isHunk ? "rgba(0,212,200,0.05)" : "transparent";
    const color = isAdd ? "var(--green)" : isRemove ? "var(--red)"
      : isHunk ? "var(--cyan)" : isMeta ? "var(--text-muted)" : "var(--text-secondary)";
    const gutter = isAdd ? "+" : isRemove ? "−" : " ";

    return (
      <div key={i} style={{ display: "flex", gap: "0", background: bg, lineHeight: "22px" }}>
        <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "11px",
          color: "var(--text-muted)", width: "28px", flexShrink: 0, textAlign: "center",
          borderRight: "0.5px solid var(--border)", userSelect: "none",
          background: "var(--bg-elevated)" }}>{i + 1}</span>
        <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "11px",
          color: "var(--text-muted)", width: "20px", flexShrink: 0, textAlign: "center",
          userSelect: "none" }}>{gutter}</span>
        <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "11px",
          color, whiteSpace: "pre", flex: 1, paddingRight: "16px" }}>
          {line.slice(isAdd || isRemove ? 1 : 0)}
        </span>
      </div>
    );
  });
}

export default function DiffViewer() {
  const [selected, setSelected] = useState<string | null>(null);

  const { data: suggestions = [], isLoading, error } = useQuery({
    queryKey: ["suggestions"],
    queryFn: () => api.suggestions().then((r) => r.data),
    refetchInterval: 30_000,
  });

  const active = suggestions.find((s) => s.patch_id === selected) ?? suggestions[0];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px",
      animation: "slideUp 0.3s ease-out both" }}>

      <div>
        <h1 style={{ fontFamily: "'Syne', sans-serif", fontSize: "13px", fontWeight: 700,
          letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--text-primary)" }}>
          Diff Viewer
        </h1>
        <p style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
          color: "var(--text-muted)", marginTop: "4px" }}>
          patch diffs from remediation suggestions
        </p>
      </div>

      {error && <ErrorBanner message="Failed to load suggestions." />}

      {isLoading ? (
        <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
          color: "var(--text-muted)" }}>loading…</div>
      ) : suggestions.length === 0 ? (
        <EmptyState message="no patches — run a scan first" />
      ) : (
        <div style={{ display: "flex", gap: "12px", minHeight: "520px" }}>

          {/* Patch list */}
          <div style={{ width: "220px", flexShrink: 0, border: "0.5px solid var(--border)",
            borderRadius: "6px", overflow: "hidden", display: "flex", flexDirection: "column" }}>
            <div style={{ padding: "8px 12px", background: "var(--bg-elevated)",
              borderBottom: "0.5px solid var(--border)",
              fontFamily: "'IBM Plex Mono', monospace", fontSize: "9px",
              letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--text-muted)" }}>
              patches · {suggestions.length}
            </div>
            <div style={{ overflowY: "auto", flex: 1 }}>
              {suggestions.map((s) => {
                const pct = Math.round(s.confidence * 100);
                const isActive = active?.patch_id === s.patch_id;
                const confColor = pct >= 80 ? "var(--green)" : pct >= 50 ? "var(--amber)" : "var(--red)";
                return (
                  <button key={s.patch_id} onClick={() => setSelected(s.patch_id)} style={{
                    width: "100%", textAlign: "left", padding: "10px 12px",
                    borderBottom: "0.5px solid var(--border)", cursor: "pointer",
                    background: isActive ? "var(--cyan-dim)" : "var(--bg-surface)",
                    borderLeft: `2px solid ${isActive ? "var(--cyan)" : "transparent"}`,
                    transition: "all 0.12s", display: "block",
                  }}
                  onMouseEnter={(e) => { if (!isActive) e.currentTarget.style.background = "var(--bg-elevated)"; }}
                  onMouseLeave={(e) => { if (!isActive) e.currentTarget.style.background = "var(--bg-surface)"; }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                      <FileCode size={10} strokeWidth={1.75}
                        style={{ color: isActive ? "var(--cyan)" : "var(--text-muted)", flexShrink: 0 }} />
                      <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "10px",
                        color: isActive ? "var(--cyan)" : "var(--text-secondary)",
                        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {s.patch_id.slice(0, 13)}
                      </span>
                    </div>
                    <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "9px",
                      color: "var(--text-muted)", marginTop: "3px",
                      overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {s.rule}
                    </div>
                    <div style={{ marginTop: "6px", display: "flex", alignItems: "center", gap: "6px" }}>
                      <div style={{ flex: 1, height: "2px", background: "var(--border)",
                        borderRadius: "1px", overflow: "hidden" }}>
                        <div style={{ height: "100%", width: `${pct}%`,
                          background: confColor, borderRadius: "1px" }} />
                      </div>
                      <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "9px",
                        color: confColor }}>{pct}%</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Diff panel */}
          <div style={{ flex: 1, border: "0.5px solid var(--border)", borderRadius: "6px",
            overflow: "hidden", display: "flex", flexDirection: "column" }}>
            {active ? (
              <>
                {/* Meta bar */}
                <div style={{ padding: "10px 16px", background: "var(--bg-elevated)",
                  borderBottom: "0.5px solid var(--border)",
                  display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "16px" }}>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      <ChevronRight size={12} strokeWidth={2} style={{ color: "var(--cyan)" }} />
                      <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "11px",
                        color: "var(--text-primary)" }}>{active.rule}</span>
                    </div>
                    <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "12px",
                      color: "var(--text-muted)", marginTop: "4px", lineHeight: 1.5, maxWidth: "520px" }}>
                      {active.explanation}
                    </p>
                  </div>
                  <div style={{ flexShrink: 0, textAlign: "right" }}>
                    <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "9px",
                      letterSpacing: "0.1em", color: "var(--text-muted)", textTransform: "uppercase" }}>
                      confidence
                    </div>
                    <div style={{ fontFamily: "'Syne', sans-serif", fontSize: "22px", fontWeight: 700,
                      color: active.confidence >= 0.8 ? "var(--green)"
                        : active.confidence >= 0.5 ? "var(--amber)" : "var(--red)",
                      lineHeight: 1.1 }}>
                      {Math.round(active.confidence * 100)}%
                    </div>
                  </div>
                </div>

                {/* Diff body */}
                <div style={{ flex: 1, overflow: "auto",
                  overflowY: "auto", background: "var(--bg-base)", padding: "8px 0" }}>
                  {active.diff
                    ? renderDiff(active.diff)
                    : <div style={{ padding: "16px", fontFamily: "'IBM Plex Mono', monospace",
                        fontSize: "11px", color: "var(--text-muted)" }}>
                        no diff available for this patch
                      </div>}
                </div>
              </>
            ) : (
              <EmptyState message="select a patch" />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
