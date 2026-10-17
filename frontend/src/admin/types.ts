// TypeScript types matching the KALX Staff Admin API (backend common/schemas/admin.py).

/** The parts of the app that jobs and audit log entries belong to (backend common/areas.py). */
export const AREAS = ['Common', 'Radio Pass Giveaway', 'KALX Workforms', 'Short Links'];

export interface JobStatus {
  id: string;
  name: string;
  /** Which part of the app the job belongs to, one of AREAS. */
  area: string;
  /** Whether the job can be run by hand (by site admins). */
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
  /** Which part of the app the event belongs to, one of AREAS. */
  area: string;
  actor_email: string | null;
  actor_role: string | null;
  entity_type: string | null;
  entity_id: number | null;
  details: Record<string, unknown> | null;
}

export interface AuditLogFilters {
  event_type?: string;
  area?: string;
  actor_email?: string;
  since?: string;
  until?: string;
  limit?: number;
  offset?: number;
}

/** A /go/<slug> short link (backend short_links/schemas/short_links.py). */
export interface ShortLink {
  id: number;
  /** Lowercase, as stored. */
  slug: string;
  target_url: string;
  note: string | null;
  created_by_email: string;
  created_at: string;
  updated_at: string;
}

export interface ShortLinkRequest {
  slug: string;
  target_url: string;
  note: string | null;
}
