import { http } from "@/api/client";

export interface AuditEvent {
  id: string;
  timestamp: string | null;
  incident_id: string | null;
  title: string;
  level: "success" | "warning" | "danger" | "info";
  detail: string;
  provider: string | null;
  model: string | null;
  source: string | null;
  patch_file: string | null;
  pr_url: string | null;
  risk_tier: string | null;
  confidence: number | null;
  row_ids: number[];
  archived_at: string | null;
  archived_by: string | null;
  count: number;
}

export async function fetchAudit(limit = 50, archived = false): Promise<AuditEvent[]> {
  const res = await http.get<AuditEvent[]>("/api/audit", { params: { limit, archived } });
  return res.data;
}

async function postIds(action: "archive" | "restore" | "delete", ids: number[]): Promise<number> {
  const res = await http.post<{ changed: number }>(`/api/audit/${action}`, { ids });
  return res.data.changed;
}

export const archiveEvents = (ids: number[]) => postIds("archive", ids);
export const restoreEvents = (ids: number[]) => postIds("restore", ids);
export const deleteEvents = (ids: number[]) => postIds("delete", ids);
