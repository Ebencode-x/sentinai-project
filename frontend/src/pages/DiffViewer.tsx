import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { format, parseISO } from "date-fns";
import { Copy } from "lucide-react";
import { api } from "@/api/client";
import { useToast } from "@/components/Toast";
import { Card, CardHeader } from "@/components/Card";

type Kind = "meta" | "hunk" | "add" | "del" | "ctx";
interface Row {
  kind: Kind;
  text: string;
  oldNo?: number;
  newNo?: number;
}

function looksLikeDiff(raw: string): boolean {
  return /^@@ /m.test(raw) || (/^--- /m.test(raw) && /^\+\+\+ /m.test(raw));
}

function parseDiff(raw: string): Row[] {
  const lines = raw.replace(/\r\n/g, "\n").split("\n");
  if (lines[lines.length - 1] === "") lines.pop();
  const rows: Row[] = [];
  let o = 0;
  let n = 0;
  let inHunk = false;
  for (const line of lines) {
    if (line.startsWith("@@")) {
      const m = /^@@ -(\d+)(?:,\d+)? \+(\d+)/.exec(line);
      if (m) {
        o = Number(m[1]);
        n = Number(m[2]);
      }
      inHunk = true;
      rows.push({ kind: "hunk", text: line });
    } else if (
      !inHunk &&
      (line.startsWith("---") || line.startsWith("+++") || line.startsWith("diff ") || line.startsWith("index "))
    ) {
      rows.push({ kind: "meta", text: line });
    } else if (line.startsWith("\\")) {
      rows.push({ kind: "meta", text: line });
    } else if (line.startsWith("+")) {
      rows.push({ kind: "add", text: line.slice(1), newNo: n++ });
    } else if (line.startsWith("-")) {
      rows.push({ kind: "del", text: line.slice(1), oldNo: o++ });
    } else {
      rows.push({ kind: "ctx", text: line.startsWith(" ") ? line.slice(1) : line, oldNo: o++, newNo: n++ });
    }
  }
  return rows;
}

const ROW_BG: Record<Kind, string> = {
  add: "var(--green-dim)",
  del: "var(--red-dim)",
  hunk: "var(--bg-panel)",
  meta: "transparent",
  ctx: "transparent",
};
const SIGN: Record<Kind, string> = { add: "+", del: "-", hunk: "", meta: "", ctx: "" };
const SIGN_COLOR: Record<Kind, string> = {
  add: "var(--green)",
  del: "var(--red)",
  hunk: "var(--text-muted)",
  meta: "var(--text-muted)",
  ctx: "var(--text-muted)",
};

function DiffBody({ patch }: { patch: string }) {
  const rows = useMemo(() => parseDiff(patch), [patch]);
  return (
    <div className="font-mono text-xs overflow-auto max-h-[560px]" style={{ background: "var(--bg-base)" }}>
      <div className="min-w-max py-2">
        {rows.map((r, i) => (
          <div
            key={i}
            className="flex min-h-[22px] leading-[22px]"
            style={{
              background: ROW_BG[r.kind],
              color: r.kind === "meta" || r.kind === "hunk" ? "var(--text-muted)" : "var(--text-primary)",
            }}
          >
            <span className="w-10 shrink-0 text-right pr-2 select-none" style={{ color: "var(--text-muted)" }}>
              {r.oldNo ?? ""}
            </span>
            <span className="w-10 shrink-0 text-right pr-2 select-none" style={{ color: "var(--text-muted)" }}>
              {r.newNo ?? ""}
            </span>
            <span className="w-5 shrink-0 text-center select-none" style={{ color: SIGN_COLOR[r.kind] }}>
              {SIGN[r.kind]}
            </span>
            <span className="whitespace-pre pr-4">{r.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function confColor(p: number): string {
  return p >= 80 ? "var(--green)" : p >= 50 ? "var(--amber)" : "var(--red)";
}

function fmt(ts: string | null | undefined): string {
  if (!ts) return "n/a";
  try {
    return format(parseISO(ts), "MMM d, HH:mm");
  } catch {
    return "n/a";
  }
}

export default function DiffViewer() {
  const { toast } = useToast();
  const [selected, setSelected] = useState<string | null>(null);

  const { data = [], isLoading, isError } = useQuery({
    queryKey: ["suggestions"],
    queryFn: () => api.suggestions().then((r) => r.data),
    refetchInterval: 30_000,
  });

  const items = useMemo(
    () => [...data].sort((a, b) => new Date(b.created_at_utc).getTime() - new Date(a.created_at_utc).getTime()),
    [data]
  );
  const active = items.find((s) => s.id === selected) ?? items[0];

  async function copyPatch() {
    if (!active?.proposed_patch) return;
    try {
      await navigator.clipboard.writeText(active.proposed_patch);
      toast("Patch copied", "ok");
    } catch {
      toast("Could not copy", "error");
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Diff</h1>
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          Patches proposed by remediation suggestions
        </p>
      </div>

      {isLoading ? (
        <div className="flex flex-col gap-2">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-16 rounded-lg animate-pulse" style={{ background: "var(--bg-surface)" }} />
          ))}
        </div>
      ) : isError ? (
        <p className="p-8 text-sm text-center" style={{ color: "var(--red)" }}>
          Could not load suggestions.
        </p>
      ) : items.length === 0 ? (
        <p className="p-8 text-sm text-center" style={{ color: "var(--text-muted)" }}>
          No patches yet. Run a scan from the Incidents page first.
        </p>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-4 items-start">
          <Card>
            <CardHeader title={`Patches (${items.length})`} />
            <ul className="max-h-[640px] overflow-y-auto">
              {items.map((s, i) => {
                const p = Math.round(s.confidence * 100);
                const isActive = active?.id === s.id;
                return (
                  <li key={s.id} style={{ borderTop: i === 0 ? undefined : "1px solid var(--border)" }}>
                    <button
                      onClick={() => setSelected(s.id)}
                      aria-current={isActive}
                      className="w-full text-left px-4 py-3 transition-colors hover:bg-[var(--bg-panel)]"
                      style={{ background: isActive ? "var(--bg-hover)" : undefined }}
                    >
                      <p className="text-sm font-medium line-clamp-2">{s.summary}</p>
                      <p className="text-xs mt-1 flex items-center gap-2" style={{ color: "var(--text-muted)" }}>
                        <span className="capitalize">{s.source}</span>
                        <span style={{ color: confColor(p) }}>{p}%</span>
                        <span>{fmt(s.created_at_utc)}</span>
                      </p>
                    </button>
                  </li>
                );
              })}
            </ul>
          </Card>

          {active && (
            <Card>
              <CardHeader
                title="Patch"
                action={
                  active.proposed_patch ? (
                    <button
                      onClick={copyPatch}
                      className="inline-flex items-center gap-1.5 text-xs font-medium"
                      style={{ color: "var(--brand)" }}
                    >
                      <Copy size={13} />
                      Copy
                    </button>
                  ) : undefined
                }
              />
              <div className="px-4 py-3">
                <p className="text-sm">{active.summary}</p>
                <p className="text-xs mt-2 flex flex-wrap gap-x-4 gap-y-1" style={{ color: "var(--text-muted)" }}>
                  <span className="capitalize">Source: {active.source}</span>
                  <span style={{ color: confColor(Math.round(active.confidence * 100)) }}>
                    Confidence: {Math.round(active.confidence * 100)}%
                  </span>
                  <span>Created: {fmt(active.created_at_utc)}</span>
                  <span className="break-all">ID: {active.id}</span>
                </p>
              </div>

              <div style={{ borderTop: "1px solid var(--border)" }}>
                {!active.proposed_patch ? (
                  <p className="p-6 text-sm text-center" style={{ color: "var(--text-muted)" }}>
                    No patch was attached to this suggestion.
                  </p>
                ) : looksLikeDiff(active.proposed_patch) ? (
                  <DiffBody patch={active.proposed_patch} />
                ) : (
                  <div>
                    <p
                      className="px-4 py-2 text-xs"
                      style={{ background: "var(--amber-dim)", color: "var(--amber)" }}
                    >
                      This patch is not a unified diff, so it cannot be applied automatically. Shown as written.
                    </p>
                    <pre
                      className="p-4 text-xs overflow-auto max-h-[560px] whitespace-pre-wrap break-words font-mono"
                      style={{ background: "var(--bg-base)", color: "var(--text-secondary)" }}
                    >
                      {active.proposed_patch}
                    </pre>
                  </div>
                )}
              </div>

              {active.proposed_code_fix?.trim() && (
                <div className="px-4 py-3" style={{ borderTop: "1px solid var(--border)" }}>
                  <p className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>Proposed fix</p>
                  <pre
                    className="text-xs rounded-md p-3 overflow-x-auto whitespace-pre-wrap break-words font-mono"
                    style={{
                      background: "var(--bg-panel)",
                      border: "1px solid var(--border)",
                      color: "var(--text-secondary)",
                    }}
                  >
                    {active.proposed_code_fix}
                  </pre>
                </div>
              )}
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
