import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";

export function useHealth() {
  const live = useQuery({
    queryKey:        ["health-live"],
    queryFn:         () => api.health.live().then((r) => r.data),
    refetchInterval: 15_000,
    retry:           1,
  });

  const ready = useQuery({
    queryKey:        ["health-ready"],
    queryFn:         () => api.health.ready().then((r) => r.data),
    refetchInterval: 30_000,
    retry:           1,
  });

  // Only mark as down if query succeeded but status is bad,
  // or if query explicitly failed (not just loading)
  const isBackendUp =
    live.isLoading || ready.isLoading
      ? null  // still connecting — don't show warning yet
      : live.isError && ready.isError
        ? false
        : true;

  return {
    live:        live.data,
    ready:       ready.data,
    isBackendUp,
    isLoading:   live.isLoading || ready.isLoading,
  };
}
