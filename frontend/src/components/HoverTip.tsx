import { useLayoutEffect, useRef } from "react";
import { createPortal } from "react-dom";
import type { TipState } from "@/hooks/useHoverTip";

const GAP = 8;
const EDGE = 8;

/** Draws the tooltip above the hovered element, or below it when there is no room. */
export default function HoverTip({ tip }: { tip: TipState | null }) {
  const ref = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!tip || !el) return;
    const w = el.offsetWidth;
    const h = el.offsetHeight;
    const left = Math.min(Math.max(tip.x - w / 2, EDGE), window.innerWidth - w - EDGE);
    const above = tip.top - h - GAP;
    el.style.left = `${left}px`;
    el.style.top = `${above >= EDGE ? above : tip.bottom + GAP}px`;
    el.style.visibility = "visible";
  }, [tip]);

  if (!tip) return null;
  return createPortal(
    <div
      ref={ref}
      role="tooltip"
      className="pointer-events-none fixed z-50 max-w-[260px] rounded-md px-3 py-2 text-xs shadow-lg"
      style={{
        left: 0,
        top: 0,
        visibility: "hidden",
        background: "var(--bg-elevated)",
        border: "1px solid var(--border-strong)",
        color: "var(--text-primary)",
      }}
    >
      {tip.content}
    </div>,
    document.body,
  );
}
