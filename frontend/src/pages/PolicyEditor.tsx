import { useState } from "react";

const EXAMPLE_POLICY = `# SentinAI Policy Configuration
# Edit and validate your security rules here.

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

export default function PolicyEditor() {
  const [content, setContent] = useState(EXAMPLE_POLICY);
  const [status, setStatus] = useState<"idle" | "ok" | "error">("idle");
  const [message, setMessage] = useState("");

  function validate() {
    // Client-side YAML structure validation
    try {
      const lines = content.split("\n");
      const hasVersion = lines.some((l) => l.trim().startsWith("version:"));
      const hasRules   = lines.some((l) => l.trim().startsWith("rules:"));
      if (!hasVersion || !hasRules) throw new Error("Missing required fields: version, rules");
      setStatus("ok");
      setMessage("Policy structure valid — ready to apply");
    } catch (e) {
      setStatus("error");
      setMessage(e instanceof Error ? e.message : "Validation failed");
    }
  }

  const lineCount = content.split("\n").length;

  return (
    <div className="space-y-6 animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-sm font-display tracking-widest text-text">POLICY EDITOR</h1>
          <p className="text-xs text-muted mt-1 tracking-wide">
            Edit sentinai-policy.yml — validate before applying
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={validate}
            className="text-xs tracking-widest px-4 py-2 border border-accent text-accent
                       hover:bg-accent hover:text-bg rounded-sm transition-all hover:shadow-glow-accent"
          >
            ◈ VALIDATE
          </button>
        </div>
      </div>

      {/* Status bar */}
      {status !== "idle" && (
        <div className={`text-xs px-4 py-2 border rounded-sm tracking-wide
          ${status === "ok"
            ? "border-ok/30 bg-ok/5 text-ok"
            : "border-warn/40 bg-warn/5 text-warn"}`}>
          {status === "ok" ? "✓" : "▲"} {message}
        </div>
      )}

      {/* Editor area */}
      <div className="border border-bg-border rounded-sm overflow-hidden">
        {/* Editor toolbar */}
        <div className="flex items-center justify-between px-4 py-2
                        bg-bg-card border-b border-bg-border">
          <span className="text-[10px] text-muted tracking-widest">
            YAML · sentinai-policy.yml
          </span>
          <div className="flex gap-4 text-[10px] text-muted">
            <span>{lineCount} lines</span>
            <span>{content.length} chars</span>
          </div>
        </div>

        {/* Line numbers + textarea */}
        <div className="flex font-mono text-xs">
          {/* Line numbers */}
          <div className="select-none bg-bg px-3 py-4 text-right text-muted/40
                          border-r border-bg-border min-w-[3rem] leading-6">
            {Array.from({ length: lineCount }, (_, i) => (
              <div key={i}>{i + 1}</div>
            ))}
          </div>

          {/* Textarea */}
          <textarea
            value={content}
            onChange={(e) => { setContent(e.target.value); setStatus("idle"); }}
            spellCheck={false}
            className="flex-1 bg-bg text-text px-4 py-4 outline-none resize-none
                       leading-6 min-h-[420px] font-mono text-xs"
          />
        </div>
      </div>

      <p className="text-[10px] text-muted/50 tracking-wider">
        // Changes are local only — apply via CLI: <span className="text-accent">sentinai apply-policy</span>
      </p>
    </div>
  );
}
