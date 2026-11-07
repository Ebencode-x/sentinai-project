import { useCallback, useState, type ReactNode } from "react";

export interface TipState {
  x: number;
  top: number;
  bottom: number;
  content: ReactNode;
}

/** State for one hover tooltip. Call show(element, content) on enter and hide() on leave. */
export function useHoverTip() {
  const [tip, setTip] = useState<TipState | null>(null);
  const show = useCallback((el: Element, content: ReactNode) => {
    const r = el.getBoundingClientRect();
    setTip({ x: r.left + r.width / 2, top: r.top, bottom: r.bottom, content });
  }, []);
  const hide = useCallback(() => setTip(null), []);
  return { tip, show, hide };
}
