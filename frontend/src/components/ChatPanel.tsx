import { useEffect, useRef, useState } from "react";
import { MessageSquare, Send, X } from "lucide-react";
import { getStoredToken } from "@/hooks/useAuth";

interface Message {
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
}

const GREETING: Message = {
  role: "assistant",
  content: "SentinAI Assistant online. Ask me about incidents, policy violations, or remediation steps.",
};

export default function ChatPanel() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([GREETING]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (open && !loading) inputRef.current?.focus();
  }, [open, loading]);

  // Stop any running stream when the panel unmounts (for example on sign out).
  useEffect(() => () => abortRef.current?.abort(), []);

  async function send() {
    const q = input.trim();
    if (!q || loading) return;
    setInput("");
    setMessages((prev) => [
      ...prev,
      { role: "user", content: q },
      { role: "assistant", content: "", streaming: true },
    ]);
    setLoading(true);

    const update = (content: string, streaming: boolean) =>
      setMessages((prev) => {
        const copy = [...prev];
        copy[copy.length - 1] = { role: "assistant", content, streaming };
        return copy;
      });

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const url = `${import.meta.env.VITE_API_URL ?? ""}/api/chat`;
      const token = getStoredToken();
      const res = await fetch(url, {
        method: "POST",
        signal: controller.signal,
        headers: {
          "Content-Type": "application/json",
          ...(token ? { "X-Session-Token": token } : {}),
        },
        body: JSON.stringify({ question: q }),
      });

      if (res.status === 401) {
        update("Your session has expired. Sign out and sign in again to keep chatting.", false);
        return;
      }
      if (!res.ok || !res.body) {
        throw new Error(`The assistant is unavailable (status ${res.status}).`);
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
              update(fullText, true);
            }
            if (parsed.error) {
              fullText = "Error: " + String(parsed.error);
              update(fullText, true);
            }
          } catch {
            /* ignore a partial or non-JSON chunk */
          }
        }
      }

      update(fullText || "No response.", false);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      update(err instanceof Error ? err.message : "Could not reach the assistant.", false);
    } finally {
      setLoading(false);
    }
  }

  function onKey(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  }

  const canSend = !loading && input.trim().length > 0;

  return (
    <>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label={open ? "Close assistant" : "Open assistant"}
        aria-expanded={open}
        className="fixed bottom-6 right-6 z-40 w-12 h-12 rounded-full flex items-center justify-center transition-transform hover:scale-105"
        style={{ background: "var(--brand)", color: "#1a1a1a", boxShadow: "0 4px 16px rgba(0,0,0,0.35)" }}
      >
        {open ? <X size={20} /> : <MessageSquare size={20} />}
      </button>

      {open && (
        <div
          className="fixed bottom-24 right-6 z-40 flex flex-col overflow-hidden rounded-lg w-[min(380px,calc(100vw-3rem))] h-[min(520px,calc(100vh-8rem))]"
          style={{
            background: "var(--bg-surface)",
            border: "1px solid var(--border-strong)",
            boxShadow: "0 12px 40px rgba(0,0,0,0.4)",
          }}
        >
          <div
            className="flex items-center gap-2 px-4 h-12 shrink-0"
            style={{ borderBottom: "1px solid var(--border)" }}
          >
            <span className="w-2 h-2 rounded-full" style={{ background: "var(--green)" }} />
            <span className="text-sm font-semibold">Assistant</span>
          </div>

          <div
            className="flex-1 overflow-y-auto p-3 flex flex-col gap-3"
            role="log"
            aria-live="polite"
          >
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className="max-w-[85%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap break-words"
                  style={
                    m.role === "user"
                      ? { background: "var(--brand)", color: "#1a1a1a" }
                      : {
                          background: "var(--bg-panel)",
                          border: "1px solid var(--border)",
                          color: "var(--text-primary)",
                        }
                  }
                >
                  {m.content}
                  {m.streaming && (
                    <span
                      className="inline-block w-1.5 h-3.5 ml-0.5 align-middle animate-pulse"
                      style={{ background: "var(--text-muted)" }}
                    />
                  )}
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>

          <div
            className="flex items-end gap-2 p-3 shrink-0"
            style={{ borderTop: "1px solid var(--border)" }}
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKey}
              placeholder="Ask about incidents or policies"
              disabled={loading}
              rows={1}
              aria-label="Message"
              className="flex-1 resize-none rounded-md px-3 py-2 text-sm outline-none transition-colors max-h-28 bg-[var(--bg-panel)] border border-[var(--border)] focus:border-[var(--brand)] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] disabled:opacity-60"
            />
            <button
              onClick={() => void send()}
              disabled={!canSend}
              aria-label="Send message"
              className="w-9 h-9 rounded-md flex items-center justify-center shrink-0 transition-opacity disabled:opacity-40"
              style={{ background: "var(--brand)", color: "#1a1a1a" }}
            >
              <Send size={16} />
            </button>
          </div>
        </div>
      )}
    </>
  );
}
