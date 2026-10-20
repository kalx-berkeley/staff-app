// TypeScript types matching backend Pydantic schemas for the KALX Staff Directory sub-site.

export interface DjPersona {
  id: number;
  name: string;
}

export interface DirectoryEntry {
  id: number;
  name: string;
  pronouns: string | null;
  email: string;
  phone: string;
  // Spinitron persona names joined with commas, and each persona on its own
  dj_name: string | null;
  dj_personas: DjPersona[];
  departments: string[];
  statuses: string[];
  titles_and_roles: string | null;
  // Changes whenever the photo does; null when there's no photo
  photo_version: string | null;
  // Leave of absence that hasn't ended yet (null once past); on_leave is true during it
  on_leave: boolean;
  loa_start: string | null;
  loa_end: string | null;
  // The years whose DJ Quiz the staff member has completed
  dj_quiz_years: number[];
}

// --- Profile page ---

/** One Sublist DJ requirement. met is null when it can't be checked. */
export interface Check {
  met: boolean | null;
  summary: string;
}

export interface LeaveCheck extends Check {
  loa_start: string | null;
  loa_end: string | null;
}

export interface PlaylistCheck {
  id: number;
  start: string;
  end: string;
  title: string | null;
  minutes: number;
  // The length of the back-to-back block it's part of, if any
  shift_minutes: number | null;
  counted: boolean;
  reason: 'automated' | 'specialty' | 'too_short' | null;
  quarter: 'previous' | 'current';
  url: string;
}

export interface ShiftCheck extends Check {
  previous_quarter: string;
  current_quarter: string;
  min_minutes: number;
  playlists: PlaylistCheck[];
  shifts_as_of: string | null;
}

export interface DepartmentCheck {
  department: string;
  hours: number;
  decision: string | null;
  counted: boolean;
}

export interface MonthCheck {
  month: string; // "YYYY-MM"
  most_recent: boolean;
  met: boolean;
  counted_hours: number;
  status: string;
  loa: boolean;
  departments: DepartmentCheck[];
  pending_departments: string[];
}

export interface WorkformsCheck extends Check {
  required_hours: number;
  months: MonthCheck[];
}

export interface QuizCheck extends Check {
  current_year: number;
  years: number[];
  this_year_deadline: string | null;
  due: string | null;
  deadline_announced: boolean;
}

export interface Eligibility {
  eligible: boolean;
  unmet: number;
  unavailable: number;
  eligible_until: string | null;
  next_workform_note: string;
  sublist: Check;
  leave: LeaveCheck;
  shift: ShiftCheck;
  workforms: WorkformsCheck;
  quiz: QuizCheck;
}

export interface WorkformMonth {
  month: string; // "YYYY-MM"
  status: 'not_started' | 'draft' | 'submitted' | 'locked';
  reported_hours: number;
  approved_hours: number;
  is_late: boolean;
  loa: boolean;
}

export interface Profile {
  entry: DirectoryEntry;
  // The editable values as Airtable holds them
  first_name: string | null;
  surname: string | null;
  // Every leave on record, including one that has ended
  loa_start: string | null;
  loa_end: string | null;
  is_self: boolean;
  // Whether the viewer can save changes (off until Airtable can be written to)
  can_edit: boolean;
  // null unless the person has a Spinitron persona or the Sublist DJ status
  eligibility: Eligibility | null;
  // The last 12 months, most recent first; null when workforms aren't available
  workforms: WorkformMonth[] | null;
}

export interface ProfileUpdate {
  first_name: string;
  surname: string | null;
  pronouns: string | null;
  phone: string | null;
  dj_persona_ids: number[];
}
