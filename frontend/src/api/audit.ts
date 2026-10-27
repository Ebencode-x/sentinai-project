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
  count: number;
}

export async function fetchAudit(limit = 50): Promise<AuditEvent[]> {
  const res = await http.get<AuditEvent[]>("/api/audit", { params: { limit } });
  return res.data;
}
