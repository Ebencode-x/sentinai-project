import axios from "axios";

/** Retry network errors, 429 and 5xx. Never retry other 4xx. At most two retries. */
export function shouldRetry(failureCount: number, err: unknown): boolean {
  if (failureCount >= 2) return false;
  if (!axios.isAxiosError(err)) return false;
  const status = err.response?.status;
  return !err.response || status === 429 || (status !== undefined && status >= 500);
}
