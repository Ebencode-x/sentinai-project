import { useState, useCallback } from "react";

const KEY = "sentinai_api_key";

export function useApiKey() {
  const [hasKey, setHasKey] = useState(() => !!localStorage.getItem(KEY));

  const setKey = useCallback((k: string) => {
    localStorage.setItem(KEY, k.trim());
    setHasKey(true);
  }, []);

  const clearKey = useCallback(() => {
    localStorage.removeItem(KEY);
    setHasKey(false);
  }, []);

  return { hasKey, setKey, clearKey };
}
