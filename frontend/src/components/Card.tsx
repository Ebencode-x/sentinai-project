import type { ReactNode } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <section
      className={`rounded-lg overflow-hidden ${className}`}
      style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
    >
      {children}
    </section>
  );
}

export function CardHeader({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <div
      className="flex items-center justify-between px-4 h-11"
      style={{ borderBottom: "1px solid var(--border)" }}
    >
      <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{title}</h2>
      {action}
    </div>
  );
}
