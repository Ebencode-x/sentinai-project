import type { ReactNode } from "react";
import StateView from "@/components/StateView";
import { useRegionState } from "@/hooks/useRegionState";
import { useRetryAll } from "@/hooks/useRetryAll";
import { selectLink, useConnectionStore } from "@/store/connection";

/** Mount only while the first load is pending, so its timer starts with the load. */
export function PendingRegion({ skeleton }: { skeleton: ReactNode }) {
  const retry = useRetryAll();
  const view = useRegionState({ pending: true, error: false, empty: false, retry });
  if (view.kind === "state") return <StateView {...view.props} />;
  return <>{skeleton}</>;
}

/** Mount only when the load failed and there is no data to show. */
export function FailedRegion() {
  const retry = useRetryAll();
  const view = useRegionState({ pending: false, error: true, empty: false, retry });
  return view.kind === "state" ? <StateView {...view.props} /> : null;
}

/** An empty result is not trusted while the link is down, so the link state wins. */
export function EmptyRegion({ title, hint }: { title: string; hint?: string }) {
  const retry = useRetryAll();
  const link = useConnectionStore(selectLink);
  const view = useRegionState({
    pending: false,
    error: link !== "online",
    empty: true,
    emptyCopy: { title, hint },
    retry,
  });
  return view.kind === "state" ? <StateView {...view.props} /> : null;
}
