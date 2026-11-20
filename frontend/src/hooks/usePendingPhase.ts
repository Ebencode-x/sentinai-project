import { useEffect, useState } from "react";

/** none: not pending. quiet: pending, too early to show anything. */
export type Phase = "none" | "quiet" | "loading" | "slow" | "timeout";

export const PHASE_MS = { show: 1_000, slow: 5_000, timeout: 60_000 } as const;

export function usePendingPhase(pending: boolean): { phase: Phase; seconds: number } {
  const [ms, setMs] = useState(0);

  useEffect(() => {
    if (!pending) return;
    const t0 = Date.now();
    const id = window.setInterval(() => setMs(Date.now() - t0), 250);
    return () => {
      window.clearInterval(id);
      setMs(0);
    };
  }, [pending]);

  const elapsed = pending ? ms : 0;
  let phase: Phase = "none";
  if (pending) {
    if (elapsed >= PHASE_MS.timeout) phase = "timeout";
    else if (elapsed >= PHASE_MS.slow) phase = "slow";
    else if (elapsed >= PHASE_MS.show) phase = "loading";
    else phase = "quiet";
  }
  return { phase, seconds: Math.floor(elapsed / 1000) };
}
