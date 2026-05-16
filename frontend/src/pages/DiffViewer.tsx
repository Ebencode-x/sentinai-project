import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import EmptyState from "@/components/EmptyState";
import ErrorBanner from "@/components/ErrorBanner";
import clsx from "clsx";

function renderDiff(raw: string) {
  return raw.split("\n").map((line, i) => {
    const isAdd    = line.startsWith("+") && !line.startsWith("+++");
    const isRemove = line.startsWith("-") && !line.startsWith("---");
    const isHunk   = line.startsWith("@@");
    const isMeta   = line.startsWith("---") || line.startsWith("+++");

    return (
      <div
        key={i}
        className={clsx(
          "flex gap-2 px-4 leading-6 text-[11px] font-mono",
          isAdd    && "bg-ok/5 text-ok",
          isRemove && "bg-red-500/5 text-red-400",
          isHunk   && "bg-accent/5 text-accent",
          isMeta   && "text-muted",
          !isAdd && !isRemove && !isHunk && !isMeta && "text-text/80"
        )}
      >
        <span className="select-none w-4 shrink-0 text-muted/40">
          {isAdd ? "+" : isRemove ? "−" : " "}
        </span>
        <span className="whitespace-pre">{line.slice(isAdd || isRemove ? 1 : 0)}</span>
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
    <div className="space-y-6 animate-slide-up">
      <div>
        <h1 className="text-sm font-display tracking-widest text-text">DIFF VIEWER</h1>
        <p className="text-xs text-muted mt-1 tracking-wide">
          Syntax-highlighted patch diffs from remediation suggestions
        </p>
      </div>

      {error && <ErrorBanner message="Failed to load suggestions." />}

      {isLoading ? (
        <div className="text-xs text-muted animate-pulse tracking-widest">LOADING…</div>
      ) : suggestions.length === 0 ? (
        <EmptyState message="NO PATCHES AVAILABLE — RUN A SCAN FIRST" />
      ) : (
        <div className="flex gap-4 min-h-[500px]">
          {/* Patch list */}
          <div className="w-64 shrink-0 border border-bg-border rounded-sm overflow-hidden">
            <div className="px-3 py-2 bg-bg-card border-b border-bg-border
                            text-[10px] text-muted tracking-widest">
              PATCHES · {suggestions.length}
            </div>
            <div className="overflow-y-auto">
              {suggestions.map((s) => {
                const pct = Math.round(s.confidence * 100);
                const isActive = active?.patch_id === s.patch_id;
                return (
                  <button
                    key={s.patch_id}
                    onClick={() => setSelected(s.patch_id)}
                    className={clsx(
                      "w-full text-left px-3 py-3 border-b border-bg-border transition-all",
                      isActive
                        ? "bg-accent/5 border-l-2 border-l-accent"
                        : "hover:bg-bg-card border-l-2 border-l-transparent"
                    )}
                  >
                    <div className="text-[10px] text-accent font-mono truncate">
                      {s.patch_id.slice(0, 14)}
                    </div>
                    <div className="text-[10px] text-muted mt-0.5 truncate">{s.rule}</div>
                    <div className="mt-1.5 flex items-center gap-1.5">
                      <div className="flex-1 h-0.5 bg-bg-border rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${
                            pct >= 80 ? "bg-ok" : pct >= 50 ? "bg-warn" : "bg-red-500"
                          }`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="text-[9px] text-muted">{pct}%</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Diff panel */}
          <div className="flex-1 border border-bg-border rounded-sm overflow-hidden flex flex-col">
            {active ? (
              <>
                {/* Patch meta */}
                <div className="px-4 py-3 bg-bg-card border-b border-bg-border flex items-start justify-between gap-4">
                  <div>
                    <div className="text-xs text-text font-mono">{active.rule}</div>
                    <div className="text-[10px] text-muted mt-1 leading-relaxed max-w-xl">
                      {active.explanation}
                    </div>
                  </div>
                  <div className="text-[10px] text-muted shrink-0 text-right">
                    <div>CONFIDENCE</div>
                    <div className={`text-base font-display ${
                      active.confidence >= 0.8 ? "text-ok" :
                      active.confidence >= 0.5 ? "text-warn" : "text-red-400"
                    }`}>
                      {Math.round(active.confidence * 100)}%
                    </div>
                  </div>
                </div>

                {/* Diff body */}
                <div className="flex-1 overflow-auto py-2 bg-bg">
                  {active.diff
                    ? renderDiff(active.diff)
                    : <div className="px-4 py-4 text-xs text-muted">No diff available for this patch.</div>
                  }
                </div>
              </>
            ) : (
              <EmptyState message="SELECT A PATCH" />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
