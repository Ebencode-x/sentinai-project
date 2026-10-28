import { useQuery } from "@tanstack/react-query";
import { fetchAudit } from "@/api/audit";

export function useAudit(limit = 50, archived = false) {
  return useQuery({
    queryKey: ["audit", limit, archived],
    queryFn: () => fetchAudit(limit, archived),
    refetchInterval: 15_000,
    staleTime: 10_000,
  });
}
