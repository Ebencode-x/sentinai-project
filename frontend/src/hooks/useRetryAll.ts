import { useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useSentinaiStore } from "@/store/sentinai";

/** One retry for every data source: React Query lists and the polling store. */
export function useRetryAll() {
  const qc = useQueryClient();
  return useCallback(() => {
    void qc.invalidateQueries();
    void useSentinaiStore.getState().fetchAll();
  }, [qc]);
}
