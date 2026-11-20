import { create } from "zustand";

export type Link = "online" | "offline" | "unreachable";

interface ConnectionState {
  browserOnline: boolean;
  failures: number;
  lastOkAt: number | null;
  reportOk: () => void;
  reportFail: () => void;
  setBrowserOnline: (online: boolean) => void;
}

const FAIL_THRESHOLD = 2;

export const useConnectionStore = create<ConnectionState>()((set) => ({
  browserOnline: typeof navigator === "undefined" ? true : navigator.onLine,
  failures: 0,
  lastOkAt: null,
  reportOk: () => set({ failures: 0, lastOkAt: Date.now() }),
  reportFail: () => set((s) => ({ failures: s.failures + 1 })),
  setBrowserOnline: (online) => set(online ? { browserOnline: true, failures: 0 } : { browserOnline: false }),
}));

if (typeof window !== "undefined") {
  window.addEventListener("online", () => useConnectionStore.getState().setBrowserOnline(true));
  window.addEventListener("offline", () => useConnectionStore.getState().setBrowserOnline(false));
}

export function selectLink(s: ConnectionState): Link {
  if (!s.browserOnline) return "offline";
  return s.failures >= FAIL_THRESHOLD ? "unreachable" : "online";
}
