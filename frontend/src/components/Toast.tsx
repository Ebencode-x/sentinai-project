import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useRef,
  type ReactNode,
} from "react";
import clsx from "clsx";

type Level = "info" | "ok" | "warn" | "error";

interface Toast {
  id:      number;
  message: string;
  level:   Level;
}

interface ToastCtx {
  toast: (message: string, level?: Level) => void;
}

const Ctx = createContext<ToastCtx>({ toast: () => undefined });

let _nextId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    const t = timers.current.get(id);
    if (t) { clearTimeout(t); timers.current.delete(id); }
  }, []);

  const toast = useCallback((message: string, level: Level = "info") => {
    const id = ++_nextId;
    setToasts((prev) => [...prev.slice(-4), { id, message, level }]);
    const t = setTimeout(() => dismiss(id), 4_000);
    timers.current.set(id, t);
  }, [dismiss]);

  useEffect(() => {
    const ts = timers.current;
    return () => ts.forEach(clearTimeout);
  }, []);

  const colors: Record<Level, string> = {
    info:  "border-accent/40  bg-accent/5  text-accent",
    ok:    "border-ok/40     bg-ok/5     text-ok",
    warn:  "border-warn/40   bg-warn/5   text-warn",
    error: "border-red-500/40 bg-red-500/5 text-red-400",
  };

  const icons: Record<Level, string> = {
    info: "◈", ok: "✓", warn: "▲", error: "✕",
  };

  return (
    <Ctx.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            onClick={() => dismiss(t.id)}
            className={clsx(
              "pointer-events-auto flex items-center gap-3 px-4 py-3",
              "border rounded-sm text-xs font-mono tracking-wide",
              "animate-slide-up cursor-pointer select-none",
              "min-w-[260px] max-w-[420px]",
              colors[t.level]
            )}
          >
            <span className="shrink-0">{icons[t.level]}</span>
            <span className="flex-1">{t.message}</span>
            <span className="shrink-0 opacity-50 text-[10px]">[×]</span>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export function useToast() {
  return useContext(Ctx);
}
