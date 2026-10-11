// TypeScript types matching the KALX Staff Admin API (backend common/schemas/admin.py).

export interface JobStatus {
  id: string;
  name: string;
  /** Which part of the app the job belongs to, e.g. "Radio Pass Giveaway". */
  area: string;
  /** Whether the job can be run by hand. */
  can_run: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
}

export interface JobRunResult {
  success: boolean;
  message: string;
}

export interface ImpersonateRequest {
  email: string | null;
  is_dj_network: boolean;
  is_station_office_network?: boolean;
}

export interface UserListItem {
  email: string;
  name: string;
  role: 'promotions' | 'staff';
}

export interface AuditLogItem {
  id: number;
  occurred_at: string;
  event_type: string;
  actor_email: string | null;
  actor_role: string | null;
  entity_type: string | null;
  entity_id: number | null;
  details: Record<string, unknown> | null;
}

export interface AuditLogFilters {
  event_type?: string;
  actor_email?: string;
  since?: string;
  until?: string;
  limit?: number;
  offset?: number;
}
