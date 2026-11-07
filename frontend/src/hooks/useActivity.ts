import { useQuery } from "@tanstack/react-query";
import { fetchActivity } from "@/api/activity";

// One request covers every range on the overview, so switching 7, 30 or 90 days
// is computed in the browser and needs no new request.
export const ACTIVITY_DAYS = 182;

export function useActivity() {
  return useQuery({
    queryKey: ["activity", ACTIVITY_DAYS],
    queryFn: () => fetchActivity(ACTIVITY_DAYS),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}
