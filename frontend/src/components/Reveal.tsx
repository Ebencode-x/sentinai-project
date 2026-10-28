import type { ReactNode } from "react";
import { useInView, useMotionProfile } from "@/hooks/useMotion";

export default function Reveal({
  children,
  delay = 0,
  className = "",
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  const m = useMotionProfile();
  const [ref, seen] = useInView<HTMLDivElement>();
  if (m === "none") return <div className={className}>{children}</div>;
  return (
    <div
      ref={ref}
      className={`ln-reveal ln-${m} ${seen ? "ln-in" : ""} ${className}`}
      style={{ transitionDelay: m === "full" ? `${delay}ms` : "0ms" }}
    >
      {children}
    </div>
  );
}
