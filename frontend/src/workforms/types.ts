export type Decision = 'Approved' | 'Denied';
export type WorkformStatus = 'not_started' | 'draft' | 'submitted' | 'locked';
/** "inside": a dated entry during a leave; "may_overlap": an undated entry in a month a leave overlaps. */
export type LoaFlag = 'inside' | 'may_overlap' | null;

export interface Entry {
  id: number;
  department: string;
  hours: number;
  description: string;
  work_date: string | null;
  loa_flag: LoaFlag;
}

export interface EntryInput {
  department: string;
  hours: number;
  description: string;
  work_date: string | null;
}

/** A department's block of a submitted workform, as Airtable has it. */
export interface DepartmentResult {
  hours: number | null;
  description: string | null;
  decision: Decision | null;
}

export interface Workform {
  month: string;
  is_open: boolean;
  is_current_month: boolean;
  deadline: string;
  status: WorkformStatus;
  has_unsent_changes: boolean;
  submitted_at: string | null;
  is_late: boolean;
  would_be_late: boolean;
  entries: Entry[];
  results: Record<string, DepartmentResult>;
  loa_start: string | null;
  loa_end: string | null;
  loa_overlaps_month: boolean;
}

export interface WorkformSummary {
  month: string;
  status: WorkformStatus;
  is_open: boolean;
  is_late: boolean;
  total_hours: number;
  results: Record<string, DepartmentResult>;
  loa_overlaps_month: boolean;
}

export interface MyWorkforms {
  open_months: string[];
  workforms: WorkformSummary[];
}

export interface Departments {
  own: string[];
  other: string[];
}

export interface Preferences {
  reminder_emails_enabled: boolean;
  review_emails_enabled: boolean;
  is_department_head: boolean;
}

export interface ReviewEntry {
  hours: number;
  description: string;
  work_date: string | null;
  loa_flag: LoaFlag;
}

export interface ReviewItem {
  airtable_record_id: string;
  staff_id: number | null;
  staff_name: string;
  hours: number | null;
  description: string | null;
  decision: Decision | null;
  entries: ReviewEntry[];
  edited_in_airtable: boolean;
  submitted_at: string | null;
  is_late: boolean;
  loa_start: string | null;
  loa_end: string | null;
  loa_overlaps_month: boolean;
}

export interface ReviewQueue {
  month: string;
  department: string;
  items: ReviewItem[];
  total: number;
  reviewed: number;
  remaining: number;
}

export interface ReviewOverview {
  is_operations_head: boolean;
  own_departments: string[];
  fallback_departments: string[];
  default_month: string;
  default_department: string;
  months: string[];
}

export interface PendingCounts {
  month: string;
  pending: Record<string, number>;
}

export interface DepartmentPerson {
  staff_id: number | null;
  staff_name: string;
  is_current_staff: boolean;
  months_reported: number;
  total_hours: number;
  /** Hours in the department in each month they reported any, by "YYYY-MM". */
  hours: Record<string, number>;
}

export interface DepartmentPeople {
  department: string;
  /** The months considered, oldest first, ending with last month. */
  months: string[];
  min_months: number;
  people: DepartmentPerson[];
}
