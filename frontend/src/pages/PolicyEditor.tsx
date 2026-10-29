import { useMemo, useState } from "react";
import { Copy, Play, RotateCcw } from "lucide-react";
import { Card, CardHeader } from "@/components/Card";
import { useToast } from "@/components/Toast";

const SAMPLE_POLICY = `# Sample policy
# Edit the rules below and run a quick check.

version: "1.0"

rules:
  - id: AUTH001
    description: "Require authentication on all admin routes"
    severity: critical
    enabled: true

  - id: PRIV001
    description: "Prevent privilege escalation via sudo"
    severity: high
    enabled: true

  - id: SEC001
    description: "Block hardcoded secrets in source"
    severity: critical
    enabled: true

  - id: TAINT001
    description: "Flag unsanitized user input in SQL"
    severity: high
    enabled: true

thresholds:
  min_confidence: 0.7
  auto_apply: false
  notify_on: [critical, high]
`.trim();

type Issue = { level: "error" | "warning"; text: string };

const SEVERITIES = new Set(["critical", "high", "medium", "low"]);
const unquote = (v: string) => v.replace(/^["']|["']$/g, "");

function checkPolicy(src: string): Issue[] {
  if (!src.trim()) return [{ level: "error", text: "The policy is empty." }];

  const issues: Issue[] = [];
  const error = (text: string) => issues.push({ level: "error", text });
  const warn = (text: string) => issues.push({ level: "warning", text });

  if (/\t/.test(src)) error("YAML does not allow tab characters for indentation.");
  if (!/^version:\s*\S+/m.test(src)) error("Missing a top-level version field.");

  const hasRules = /^rules:\s*$/m.test(src);
  if (!hasRules) error("Missing a top-level rules: list.");

  const ids = Array.from(src.matchAll(/^\s*-\s*id:\s*(\S+)/gm), (m) => unquote(m[1]));
  if (hasRules && ids.length === 0) error("The rules list has no entries.");

  const seen = new Set<string>();
  const dupes = new Set<string>();
  ids.forEach((id) => {
    if (seen.has(id)) dupes.add(id);
    seen.add(id);
  });
  dupes.forEach((id) => error(`Rule id "${id}" appears more than once.`));

  for (const m of src.matchAll(/^\s*severity:\s*(\S+)/gm)) {
    if (!SEVERITIES.has(unquote(m[1]).toLowerCase())) {
      error(`Unknown severity "${unquote(m[1])}". Use critical, high, medium or low.`);
    }
  }
  const severityCount = (src.match(/^\s*severity:/gm) ?? []).length;
  if (ids.length > 0 && severityCount < ids.length) warn("Some rules have no severity.");

  const conf = src.match(/^\s*min_confidence:\s*(\S+)/m);
  if (conf) {
    const v = Number(conf[1]);
    if (!Number.isFinite(v) || v < 0 || v > 1) error("min_confidence must be a number between 0 and 1.");
  }

  return issues;
}

const BTN_GHOST =
  "inline-flex items-center gap-2 rounded-md px-3 h-8 text-sm font-medium transition-colors " +
  "border border-(--border-strong) text-(--text-secondary) " +
  "hover:text-(--text-primary) hover:bg-(--bg-hover)";

export default function PolicyEditor() {
  const { toast } = useToast();
  const [content, setContent] = useState(SAMPLE_POLICY);
  const [issues, setIssues] = useState<Issue[] | null>(null);

  const lineCount = useMemo(() => content.split("\n").length, [content]);
  const hasError = issues?.some((i) => i.level === "error") ?? false;

  async function copy() {
    try {
      await navigator.clipboard.writeText(content);
      toast("Copied to clipboard", "ok");
    } catch {
      toast("Could not copy", "error");
    }
  }

  function reset() {
    if (content !== SAMPLE_POLICY && !window.confirm("Replace your edits with the sample policy?")) return;
    setContent(SAMPLE_POLICY);
    setIssues(null);
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Policy</h1>
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            A scratchpad for policy drafts. Changes stay in this browser tab and are not saved to the server.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button className={BTN_GHOST} onClick={reset}>
            <RotateCcw size={14} />
            Reset
          </button>
          <button className={BTN_GHOST} onClick={copy}>
            <Copy size={14} />
            Copy
          </button>
          <button
            onClick={() => setIssues(checkPolicy(content))}
            className="inline-flex items-center gap-2 rounded-md px-3.5 h-8 text-sm font-medium"
            style={{ background: "var(--brand)", color: "#1a1a1a" }}
          >
            <Play size={14} />
            Run check
          </button>
        </div>
      </div>

      {issues &&
        (issues.length === 0 ? (
          <p className="rounded-md px-3 py-2 text-sm" style={{ background: "var(--green-dim)", color: "var(--green)" }}>
            Structure looks fine. This is a quick check, not a full YAML parse.
          </p>
        ) : (
          <ul
            className="rounded-md px-3 py-2 text-sm flex flex-col gap-1"
            style={{ background: hasError ? "var(--red-dim)" : "var(--amber-dim)" }}
          >
            {issues.map((i, n) => (
              <li key={n} style={{ color: i.level === "error" ? "var(--red)" : "var(--amber)" }}>
                {i.text}
              </li>
            ))}
          </ul>
        ))}

      <Card>
        <CardHeader
          title="sentinai-policy.yml"
          action={
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>
              {lineCount} lines
            </span>
          }
        />
        <div className="flex font-mono text-xs overflow-auto max-h-[70vh]" style={{ background: "var(--bg-base)" }}>
          <div
            className="select-none text-right px-3 py-3 shrink-0"
            style={{ color: "var(--text-muted)", borderRight: "1px solid var(--border)", lineHeight: "24px" }}
            aria-hidden="true"
          >
            {Array.from({ length: lineCount }, (_, i) => (
              <div key={i}>{i + 1}</div>
            ))}
          </div>
          <textarea
            value={content}
            onChange={(e) => {
              setContent(e.target.value);
              setIssues(null);
            }}
            spellCheck={false}
            wrap="off"
            aria-label="Policy YAML"
            className="flex-1 min-w-0 px-4 py-3 outline-hidden resize-none bg-transparent whitespace-pre overflow-x-auto"
            style={{ color: "var(--text-primary)", lineHeight: "24px" }}
          />
        </div>
      </Card>
    </div>
  );
}
