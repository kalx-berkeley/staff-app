// TypeScript types matching backend Pydantic schemas: identity and errors shared by every sub-site.

// Profile types
export interface PromotionsStaffProfile {
  id: number;
  name: string;
  phone: string;
  dj_name?: string | null;
  is_sublist_dj: boolean;
  // Leave of absence (YYYY-MM-DD, inclusive); either may be null
  loa_start?: string | null;
  loa_end?: string | null;
}

export interface StaffProfile {
  id: number;
  name: string;
  phone: string;
  dj_name: string | null;
  is_sublist_dj: boolean;
  // Leave of absence (YYYY-MM-DD, inclusive); either may be null
  loa_start?: string | null;
  loa_end?: string | null;
}

// User types
export type UserRole = 'promotions' | 'staff' | 'dj' | 'unauthorized';

export interface UserResponse {
  email: string | null;
  real_email?: string | null;
  real_name?: string | null;
  role: UserRole;
  is_dj_network: boolean;
  is_station_office_network: boolean;
  is_staging?: boolean;
  impersonating_email?: string | null;
  is_impersonating_dj_network?: boolean;
  is_impersonating_station_office_network?: boolean;
  profile?: PromotionsStaffProfile | StaffProfile | null;
}

// API Error types
export interface APIError {
  detail: string | ValidationError[];
  retry_after?: number;
}

export interface ValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
}

// Sync result types
export interface SyncResult {
  promotions_upserted: string[];
  staff_upserted: string[];
  deactivated: string[];
  errors: string[];
}
