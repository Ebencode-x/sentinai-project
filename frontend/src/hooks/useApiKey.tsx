import { createContext, useContext, useState, useCallback, ReactNode } from "react";

const KEY     = "sentinai_api_key";
const EXPIRY  = "sentinai_key_expiry";
const TTL_MS  = 8 * 60 * 60 * 1000; // 8 hours

function isExpired(): boolean {
  const exp = localStorage.getItem(EXPIRY);
  if (!exp) return true;
  return Date.now() > parseInt(exp, 10);
}

interface ApiKeyContextValue {
  hasKey: boolean;
  setKey: (k: string) => void;
  clearKey: () => void;
}

const ApiKeyContext = createContext<ApiKeyContextValue | null>(null);

export function ApiKeyProvider({ children }: { children: ReactNode }) {
  const [hasKey, setHasKey] = useState(() => {
    const key = localStorage.getItem(KEY);
    if (!key || isExpired()) {
      localStorage.removeItem(KEY);
      localStorage.removeItem(EXPIRY);
      return false;
    }
    return true;
  });

  const setKey = useCallback((k: string) => {
    localStorage.setItem(KEY,    k.trim());
    localStorage.setItem(EXPIRY, String(Date.now() + TTL_MS));
    setHasKey(true);
  }, []);

  const clearKey = useCallback(() => {
    localStorage.removeItem(KEY);
    localStorage.removeItem(EXPIRY);
    setHasKey(false);
  }, []);

  return (
    <ApiKeyContext.Provider value={{ hasKey, setKey, clearKey }}>
      {children}
    </ApiKeyContext.Provider>
  );
}

export function useApiKey() {
  const ctx = useContext(ApiKeyContext);
  if (!ctx) throw new Error("useApiKey must be used within an ApiKeyProvider");
  return ctx;
}
