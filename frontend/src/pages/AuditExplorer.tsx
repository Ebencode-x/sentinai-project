import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type Suggestion } from "@/api/client";
import { format, parseISO } from "date-fns";
import EmptyState from "@/components/EmptyState";
import ErrorBanner from "@/components/ErrorBanner";

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
    <div className="space-y-6 animate-slide-up">
      {/* Header */}
      <div>
        <h1 className="text-sm font-display tracking-widest text-text">AUDIT EXPLORER</h1>
        <p className="text-xs text-muted mt-1 tracking-wide">
          Searchable record of AI remediation suggestions
        </p>
      </div>

      {/* Search */}
      <div className="relative">
        <span className="absolute left-4 top-1/2 -translate-y-1/2 text-muted text-xs">SEARCH //</span>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="rule, explanation, patch_id…"
          className="w-full bg-bg-card border border-bg-border text-text text-xs
                     pl-[88px] pr-4 py-3 font-mono rounded-sm outline-none
                     focus:border-accent transition-all placeholder:text-muted/40"
        />
        {q && (
          <button
            onClick={() => setQ("")}
            className="absolute right-4 top-1/2 -translate-y-1/2 text-muted hover:text-text text-xs"
          >
            [CLR]
          </button>
        )}
      </div>

      {/* Count */}
      <div className="text-xs text-muted tracking-wider">
        {filtered.length} of {suggestions.length} records
      </div>

      {error && <ErrorBanner message="Failed to load suggestions." />}

      {/* Table */}
      {isLoading ? (
        <div className="text-xs text-muted animate-pulse tracking-widest">LOADING…</div>
      ) : filtered.length === 0 ? (
        <EmptyState message="NO RECORDS FOUND" />
      ) : (
        <div className="border border-bg-border rounded-sm overflow-hidden">
          {/* Header row */}
          <div className="grid grid-cols-[1fr_2fr_auto_auto] gap-4 px-4 py-2
                          bg-bg-card border-b border-bg-border
                          text-[10px] text-muted tracking-widest uppercase">
            <span>PATCH ID</span>
            <span>RULE / EXPLANATION</span>
            <span>CONFIDENCE</span>
            <span>TIME</span>
          </div>

          {filtered.map((s, i) => (
            <AuditRow key={s.patch_id} suggestion={s} index={i} total={filtered.length} />
          ))}
        </div>
      )}
    </div>
  );
}

function AuditRow({
  suggestion: s,
  index,
  total,
}: {
  suggestion: Suggestion;
  index: number;
  total: number;
}) {
  const [open, setOpen] = useState(false);
  const pct = Math.round(s.confidence * 100);

  const ts = (() => {
    try { return s.created_at ? format(parseISO(s.created_at), "MMM dd HH:mm") : "—"; }
    catch { return "—"; }
  })();

  const barColor =
    pct >= 80 ? "bg-ok"   :
    pct >= 50 ? "bg-warn" : "bg-red-500";

  return (
    <>
      <div
        onClick={() => setOpen((o) => !o)}
        className={`grid grid-cols-[1fr_2fr_auto_auto] gap-4 px-4 py-3 cursor-pointer
                    text-xs border-b transition-all hover:bg-bg-card/60
                    ${index === total - 1 ? "border-transparent" : "border-bg-border"}`}
      >
        <span className="text-accent font-mono text-[11px] truncate" title={s.patch_id}>
          {s.patch_id.slice(0, 12)}…
        </span>
        <span className="text-text truncate" title={s.explanation}>
          <span className="text-muted">{s.rule}</span>
          {" · "}
          {s.explanation.slice(0, 60)}{s.explanation.length > 60 ? "…" : ""}
        </span>
        <div className="flex items-center gap-2 w-20">
          <div className="flex-1 h-1 bg-bg-border rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${barColor}`}
              style={{ width: `${pct}%` }}
            />
          </div>
          <span className={`text-[10px] w-7 text-right ${barColor.replace("bg-", "text-")}`}>
            {pct}%
          </span>
        </div>
        <span className="text-muted w-20 text-right">{ts}</span>
      </div>

      {open && (
        <div className="px-4 py-3 bg-bg border-b border-bg-border animate-fade-in">
          <div className="text-[10px] text-muted tracking-wider mb-2">FULL EXPLANATION</div>
          <p className="text-xs text-text leading-relaxed">{s.explanation}</p>
          <div className="mt-2 text-[10px] text-muted/60">
            PATCH_ID: {s.patch_id}
          </div>
        </div>
      )}
    </>
  );
}
