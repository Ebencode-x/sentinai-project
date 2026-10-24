import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useRef,
  type ReactNode,
} from "react";
import { X } from "lucide-react";

type Level = "info" | "ok" | "warn" | "error";

interface Toast {
  id: number;
  message: string;
  level: Level;
}

interface ToastCtx {
  toast: (message: string, level?: Level) => void;
}

const Ctx = createContext<ToastCtx>({ toast: () => undefined });

let _nextId = 0;

const DOT: Record<Level, string> = {
  info: "var(--text-muted)",
  ok: "var(--green)",
  warn: "var(--amber)",
  error: "var(--red)",
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    const t = timers.current.get(id);
    if (t) {
      clearTimeout(t);
      timers.current.delete(id);
    }
  }, []);

  const toast = useCallback(
    (message: string, level: Level = "info") => {
      const id = ++_nextId;
      setToasts((prev) => [...prev.slice(-4), { id, message, level }]);
      timers.current.set(
        id,
        setTimeout(() => dismiss(id), 4_000)
      );
    },
    [dismiss]
  );

  useEffect(() => {
    const ts = timers.current;
    return () => ts.forEach(clearTimeout);
  }, []);

  return (
    <Ctx.Provider value={{ toast }}>
      {children}
      <div
        className="fixed top-16 right-4 z-50 flex flex-col gap-2 pointer-events-none"
        role="status"
        aria-live="polite"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            className="pointer-events-auto flex items-center gap-3 rounded-lg px-4 py-3 text-sm min-w-[260px] max-w-[420px] animate-fade-in"
            style={{
              background: "var(--bg-elevated)",
              border: "1px solid var(--border-strong)",
              color: "var(--text-primary)",
              boxShadow: "0 8px 24px rgba(0,0,0,0.35)",
            }}
          >
            <span className="w-2 h-2 rounded-full shrink-0" style={{ background: DOT[t.level] }} />
            <span className="flex-1">{t.message}</span>
            <button
              onClick={() => dismiss(t.id)}
              aria-label="Dismiss"
              className="shrink-0 transition-colors text-[var(--text-muted)] hover:text-[var(--text-primary)]"
            >
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export function useToast() {
  return useContext(Ctx);
}
