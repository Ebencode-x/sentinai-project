import { useQuery } from "@tanstack/react-query";
import { fetchAudit } from "@/api/audit";

export function useAudit(limit = 50) {
  return useQuery({
    queryKey: ["audit", limit],
    queryFn: () => fetchAudit(limit),
    refetchInterval: 15_000,
    staleTime: 10_000,
  });
}
