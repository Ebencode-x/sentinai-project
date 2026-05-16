import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";

/**
 * Centralized health polling used by Layout and any component
 * that needs to reflect backend status.
 */
export function useHealth() {
  const live = useQuery({
    queryKey:       ["health-live"],
    queryFn:        () => api.health.live().then((r) => r.data),
    refetchInterval: 15_000,
    retry:           1,
  });

  const ready = useQuery({
    queryKey:       ["health-ready"],
    queryFn:        () => api.health.ready().then((r) => r.data),
    refetchInterval: 30_000,
    retry:           1,
  });

  const isBackendUp =
    live.data?.status === "ok" || ready.data?.healthy === true;

  return {
    live:        live.data,
    ready:       ready.data,
    isBackendUp,
    isLoading:   live.isLoading || ready.isLoading,
  };
}
