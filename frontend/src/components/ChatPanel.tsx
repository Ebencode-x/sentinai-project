import { useState, useRef, useEffect } from "react";
import { getApiKey } from "@/api/client";

interface Message {
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
}

export default function ChatPanel() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "SentinAI Assistant online. Ask me about incidents, policy violations, or remediation steps.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 100);
  }, [open]);

  async function send() {
    const q = input.trim();
    if (!q || loading) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setLoading(true);

    const assistantIdx = messages.length + 1;
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "", streaming: true },
    ]);

    try {
      const BASE = import.meta.env.VITE_API_URL ?? "/api";
      const url = BASE === "/api" ? "/api/chat" : BASE + "/chat";
      const key = getApiKey();
      const res = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(key ? { "X-API-Key": key } : {}),
        },
        body: JSON.stringify({ question: q }),
      });

      if (!res.ok || !res.body) {
        throw new Error("Request failed: " + res.status);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let fullText = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";
        for (const part of parts) {
          const line = part.startsWith("data: ") ? part.slice(6) : part;
          if (line === "[DONE]") break;
          try {
            const parsed = JSON.parse(line);
            if (parsed.token) {
              fullText += parsed.token;
              setMessages((prev) => {
                const copy = [...prev];
                copy[copy.length - 1] = {
                  role: "assistant",
                  content: fullText,
                  streaming: true,
                };
                return copy;
              });
            }
            if (parsed.error) {
              fullText = parsed.error;
              setMessages((prev) => {
                const copy = [...prev];
                copy[copy.length - 1] = {
                  role: "assistant",
                  content: "Error: " + parsed.error,
                  streaming: false,
                };
                return copy;
              });
            }
          } catch {}
        }
      }

      setMessages((prev) => {
        const copy = [...prev];
        copy[copy.length - 1] = {
          role: "assistant",
          content: fullText || "No response.",
          streaming: false,
        };
        return copy;
      });
    } catch (err: any) {
      setMessages((prev) => {
        const copy = [...prev];
        copy[copy.length - 1] = {
          role: "assistant",
          content: "Connection error: " + err.message,
          streaming: false,
        };
        return copy;
      });
    } finally {
      setLoading(false);
    }
  }

  function onKey(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <>
      {/* Floating trigger */}
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          position: "fixed",
          bottom: "24px",
          right: "24px",
          width: "48px",
          height: "48px",
          borderRadius: "50%",
          background: open ? "var(--cyan)" : "var(--bg-elevated)",
          border: "1px solid var(--cyan)",
          color: open ? "var(--bg-base)" : "var(--cyan)",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 1000,
          transition: "all 0.2s",
          boxShadow: "0 0 16px color-mix(in srgb, var(--cyan) 30%, transparent)",
        }}
        title="SentinAI Assistant"
      >
        {open ? (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        ) : (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
        )}
      </button>

      {/* Chat panel */}
      {open && (
        <div
          style={{
            position: "fixed",
            bottom: "84px",
            right: "24px",
            width: "360px",
            height: "480px",
            background: "var(--bg-surface)",
            border: "0.5px solid var(--border)",
            borderRadius: "12px",
            display: "flex",
            flexDirection: "column",
            zIndex: 999,
            boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
            overflow: "hidden",
          }}
        >
          {/* Header */}
          <div
            style={{
              padding: "12px 16px",
              borderBottom: "0.5px solid var(--border)",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              background: "var(--bg-elevated)",
            }}
          >
            <div
              style={{
                width: "6px",
                height: "6px",
                borderRadius: "50%",
                background: "var(--cyan)",
                boxShadow: "0 0 6px var(--cyan)",
              }}
            />
            <span
              style={{
                fontFamily: "'IBM Plex Mono', monospace",
                fontSize: "11px",
                fontWeight: 600,
                letterSpacing: "0.1em",
                color: "var(--text-secondary)",
                textTransform: "uppercase",
              }}
            >
              SentinAI Assistant
            </span>
            <span
              style={{
                marginLeft: "auto",
                fontFamily: "'IBM Plex Mono', monospace",
                fontSize: "9px",
                color: "var(--text-muted)",
              }}
            >
              live context
            </span>
          </div>

          {/* Messages */}
          <div
            style={{
              flex: 1,
              overflowY: "auto",
              padding: "12px",
              display: "flex",
              flexDirection: "column",
              gap: "10px",
            }}
          >
            {messages.map((msg, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: msg.role === "user" ? "flex-end" : "flex-start",
                }}
              >
                <div
                  style={{
                    maxWidth: "85%",
                    padding: "8px 12px",
                    borderRadius: msg.role === "user" ? "12px 12px 2px 12px" : "12px 12px 12px 2px",
                    background: msg.role === "user" ? "var(--cyan-dim)" : "var(--bg-elevated)",
                    border: "0.5px solid",
                    borderColor: msg.role === "user" ? "var(--cyan)" : "var(--border)",
                    fontFamily: "'DM Sans', sans-serif",
                    fontSize: "12px",
                    lineHeight: "1.6",
                    color: msg.role === "user" ? "var(--cyan)" : "var(--text-secondary)",
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                  }}
                >
                  {msg.content}
                  {msg.streaming && (
                    <span
                      style={{
                        display: "inline-block",
                        width: "6px",
                        height: "12px",
                        background: "var(--cyan)",
                        marginLeft: "2px",
                        animation: "blink 0.8s step-end infinite",
                        verticalAlign: "middle",
                      }}
                    />
                  )}
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div
            style={{
              padding: "10px 12px",
              borderTop: "0.5px solid var(--border)",
              display: "flex",
              gap: "8px",
              alignItems: "flex-end",
              background: "var(--bg-elevated)",
            }}
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKey}
              placeholder="Ask about incidents, policies..."
              disabled={loading}
              rows={1}
              style={{
                flex: 1,
                background: "var(--bg-base)",
                border: "0.5px solid var(--border)",
                borderRadius: "6px",
                padding: "8px 10px",
                color: "var(--text-primary)",
                fontFamily: "'IBM Plex Mono', monospace",
                fontSize: "11px",
                resize: "none",
                outline: "none",
                lineHeight: "1.5",
              }}
            />
            <button
              onClick={send}
              disabled={loading || !input.trim()}
              style={{
                background: loading || !input.trim() ? "var(--bg-base)" : "var(--cyan-dim)",
                border: "0.5px solid var(--cyan)",
                borderRadius: "6px",
                padding: "8px 12px",
                color: loading || !input.trim() ? "var(--text-muted)" : "var(--cyan)",
                cursor: loading || !input.trim() ? "not-allowed" : "pointer",
                fontFamily: "'IBM Plex Mono', monospace",
                fontSize: "10px",
                transition: "all 0.15s",
              }}
            >
              {loading ? "..." : "Send"}
            </button>
          </div>
        </div>
      )}

      <style>{`
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
      `}</style>
    </>
  );
}
