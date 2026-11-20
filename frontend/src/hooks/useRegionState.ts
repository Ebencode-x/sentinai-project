import type { PenguinMood } from "@/components/Penguin";
import { usePendingPhase } from "@/hooks/usePendingPhase";
import { COPY_TIMEOUT, COPY_UNREACHABLE, STATE_COPY } from "@/lib/stateCopy";
import { selectLink, useConnectionStore } from "@/store/connection";

export interface RegionInput {
  /** First load in flight and there is no data to show yet. */
  pending: boolean;
  /** The load failed and there is no data to show. */
  error: boolean;
  /** Loaded fine, but there is nothing to list. */
  empty: boolean;
  emptyCopy?: { title: string; hint?: string };
  retry?: () => void;
}

export interface StateProps {
  mood: PenguinMood;
  title: string;
  hint?: string;
  action?: { label: string; onClick: () => void };
}

export type RegionView =
  | { kind: "data" }
  | { kind: "quiet" }
  | { kind: "state"; props: StateProps };

export function useRegionState(input: RegionInput): RegionView {
  const { pending, error, empty, emptyCopy, retry } = input;
  const link = useConnectionStore(selectLink);
  const { phase, seconds } = usePendingPhase(pending);
  const action = retry ? { label: "Try again", onClick: retry } : undefined;

  if ((pending || error) && link === "offline") {
    return { kind: "state", props: { mood: "offline", ...STATE_COPY.offline, action } };
  }
  if (error) {
    if (link === "unreachable") {
      return { kind: "state", props: { mood: "slow", ...COPY_UNREACHABLE, action } };
    }
    return { kind: "state", props: { mood: "error", ...STATE_COPY.error, action } };
  }
  if (pending) {
    if (phase === "loading") {
      return { kind: "state", props: { mood: "loading", ...STATE_COPY.loading } };
    }
    if (phase === "slow") {
      const hint = `${STATE_COPY.slow.hint} ${seconds} seconds so far.`;
      return { kind: "state", props: { mood: "slow", title: STATE_COPY.slow.title, hint } };
    }
    if (phase === "timeout") {
      return { kind: "state", props: { mood: "error", ...COPY_TIMEOUT, action } };
    }
    return { kind: "quiet" };
  }
  if (empty) {
    return { kind: "state", props: { mood: "empty", ...(emptyCopy ?? STATE_COPY.empty) } };
  }
  return { kind: "data" };
}
