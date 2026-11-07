import { http } from "@/api/client";

export interface DayActivity {
  date: string;
  events: number;
  new_incidents: number;
  resolved: number;
}

export interface ActivityTotals {
  events: number;
  new_incidents: number;
  resolved: number;
  active_days: number;
  longest_streak: number;
  current_streak: number;
}

export interface SourceActivity {
  id: string;
  name: string;
  status: "active" | "revoked";
  last_event_at: string | null;
  daily: number[];
}

export interface ActivityReport {
  days: number;
  daily: DayActivity[];
  totals: ActivityTotals;
  sources: SourceActivity[];
}

export async function fetchActivity(days = 182): Promise<ActivityReport> {
  const res = await http.get<ActivityReport>("/api/activity/daily", { params: { days } });
  return res.data;
}
