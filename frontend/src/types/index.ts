// TypeScript types matching backend Pydantic schemas

// Specialty show types
export interface SpecialtyShowCreate {
  name: string;
  owner_emails?: string[];
}

export interface SpecialtyShowUpdate {
  name?: string;
  owner_emails?: string[] | null;
  dj_names?: string[] | null;
}

export interface SpecialtyShowResponse {
  id: number;
  name: string;
  deleted: boolean;
  owner_emails: string[];
  dj_names: string[];
}

// Promoter types
export interface PromoterContactCreate {
  name?: string | null;
  title?: string | null;
  email?: string | null;
  phone?: string | null;
}

export interface PromoterContactResponse extends PromoterContactCreate {
  id: number;
}

export interface PromoterCreate {
  name: string;
  pass_call_instructions?: string | null;
  requires_phone_number?: boolean;
  requires_email_address?: boolean;
  staff_guest_requires_name?: boolean;
  owner_emails?: string[];
  contacts?: PromoterContactCreate[];
}

export interface PromoterUpdate {
  name?: string;
  pass_call_instructions?: string | null;
  requires_phone_number?: boolean;
  requires_email_address?: boolean;
  staff_guest_requires_name?: boolean;
  owner_emails?: string[];
  contacts?: PromoterContactCreate[];
}

export interface PromoterResponse {
  id: number;
  name: string;
  pass_call_instructions: string | null;
  requires_phone_number: boolean;
  requires_email_address: boolean;
  staff_guest_requires_name: boolean;
  deleted: boolean;
  owner_emails: string[];
  contacts: PromoterContactResponse[];
}

// Venue types
export interface VenueContactCreate {
  name?: string | null;
  title?: string | null;
  email?: string | null;
  phone?: string | null;
}

export interface VenueContactResponse extends VenueContactCreate {
  id: number;
}

export interface VenueCreate {
  name: string;
  address: string;
  pass_call_instructions?: string | null;
  win_frequency_days?: number | null;
  default_wheelchair_accessible?: boolean | null;
  default_age_restriction?: AgeRestriction | null;
  default_num_pass_pairs?: number | null;
  requires_phone_number?: boolean;
  requires_email_address?: boolean;
  staff_guest_requires_name?: boolean;
  default_lottery_enabled?: boolean;
  default_lottery_window_hours?: number;
  default_dj_preassign_prohibition_days?: number | null;
  default_close_hours_before_show?: number | null;
  promoter_id?: number | null;
  shows_have_external_promoter?: boolean;
  owner_emails?: string[];
  contacts?: VenueContactCreate[];
}

export interface VenueUpdate {
  name?: string;
  address?: string;
  pass_call_instructions?: string | null;
  win_frequency_days?: number | null;
  default_wheelchair_accessible?: boolean | null;
  default_age_restriction?: AgeRestriction | null;
  default_num_pass_pairs?: number | null;
  requires_phone_number?: boolean;
  requires_email_address?: boolean;
  staff_guest_requires_name?: boolean;
  default_lottery_enabled?: boolean;
  default_lottery_window_hours?: number;
  default_dj_preassign_prohibition_days?: number | null;
  default_close_hours_before_show?: number | null;
  promoter_id?: number | null;
  shows_have_external_promoter?: boolean;
  owner_emails?: string[];
  contacts?: VenueContactCreate[];
}

export interface VenueResponse {
  id: number;
  name: string;
  address: string;
  pass_call_instructions: string | null;
  win_frequency_days: number | null;
  default_wheelchair_accessible: boolean | null;
  default_age_restriction: AgeRestriction | null;
  default_num_pass_pairs: number | null;
  requires_phone_number: boolean;
  requires_email_address: boolean;
  staff_guest_requires_name: boolean;
  default_lottery_enabled: boolean;
  default_lottery_window_hours: number;
  default_dj_preassign_prohibition_days: number | null;
  default_close_hours_before_show: number | null;
  has_logo: boolean;
  deleted: boolean;
  promoter_id?: number | null;
  promoter?: PromoterResponse | null;
  shows_have_external_promoter: boolean;
  owner_emails: string[];
  contacts: VenueContactResponse[];
}

// Profile types
export interface PromotionsStaffProfile {
  name: string;
  phone: string;
  dj_name?: string | null;
}

export interface StaffProfile {
  name: string;
  phone: string;
  dj_name: string | null;
  is_sublist_dj: boolean;
}

// MusicBrainz types
export interface MusicBrainzArtist {
  id: string;
  name: string;
  type?: string | null;
  country?: string | null;
  disambiguation?: string | null;
  score?: number;
  tags?: string[];
}

export interface ShowBandCreate {
  musicbrainz_id: string;
  band_name: string;
  start_pos: number;
  end_pos: number;
  artist_type?: string | null;
  artist_country?: string | null;
  artist_disambiguation?: string | null;
  artist_tags?: string[] | null;
}

export interface ShowBand extends ShowBandCreate {
  id: number;
  show_id: number;
}

// Show types
export type AgeRestriction = 'all_ages' | '18+' | '21+';
export type ShowStatus = 'draft' | 'published' | 'closed' | 'deleted';

export interface ShowCreate {
  event_name: string;
  genre: string[];
  venue_id: number;
  promoter_id?: number | null;
  show_date: string; // ISO date string (end date for multi-day shows)
  show_time?: string | null; // HH:MM format; omit for multi-day shows
  show_start_date?: string | null; // ISO date string; set for multi-day shows
  on_air_description?: string | null;
  caller_special_instructions?: string | null;
  age_restriction: AgeRestriction;
  wheelchair_accessible: boolean;
  num_pass_pairs: number; // 1-5
  planned_close_date?: string | null;
  planned_close_time?: string | null;
  auto_close?: boolean;
  co_announce?: boolean;
  lottery_enabled?: boolean;
  lottery_window_hours?: number;
  dj_preassign_prohibition_days?: number | null;
  bands?: ShowBandCreate[];
}

export interface ShowUpdate {
  event_name?: string;
  genre?: string[];
  venue_id?: number;
  promoter_id?: number | null;
  show_date?: string;
  show_time?: string | null;
  show_start_date?: string | null;
  on_air_description?: string | null;
  caller_special_instructions?: string | null;
  age_restriction?: AgeRestriction;
  wheelchair_accessible?: boolean;
  num_pass_pairs?: number;
  planned_close_date?: string | null;
  planned_close_time?: string | null;
  auto_close?: boolean;
  co_announce?: boolean;
  lottery_enabled?: boolean;
  lottery_window_hours?: number;
  dj_preassign_prohibition_days?: number | null;
  bands?: ShowBandCreate[] | null;
}

export interface PromotionsContact {
  email: string;
  name: string;
  phone: string;
}

export interface ShowAttempt {
  id: number;
  dj_name: string;
  attempted_at: string; // ISO datetime string
}

export interface LotteryEntryResponse {
  id: number;
  show_id: number;
  entry_type: string;
  staff_id: number | null;
  staff_name?: string | null;
  dj_name: string | null;
  specialty_show_id?: number | null;
  assignment_date: string | null;
  has_guest: boolean;
  guest_name: string | null;
  only_attend_with_guest: boolean;
  status: string;
  entered_at: string;
}

export interface LotteryStatus {
  is_active: boolean;
  deadline: string | null;
  staff_entry_count: number;
  dj_entry_count: number;
  my_staff_entry: LotteryEntryResponse | null;
  my_dj_entry: LotteryEntryResponse | null;
  all_staff_entries?: LotteryEntryResponse[] | null;
  all_dj_entries?: LotteryEntryResponse[] | null;
}

export interface LotteryScheduleItem {
  show_id: number;
  event_name: string;
  venue_name: string;
  lottery_deadline: string;
  staff_entry_count: number;
  dj_entry_count: number;
  show_status: string;
  schedule_status: 'scheduled' | 'past' | 'executed';
}

export interface StaffLotteryEntryCreate {
  has_guest?: boolean;
  guest_name?: string | null;
  only_attend_with_guest?: boolean;
}

export interface DJLotteryEntryCreate {
  assignment_date: string;
  specialty_show_id?: number | null;
  dj_name_override?: string | null;
}

export interface AffectedStaffMember {
  name: string;
  phone: string | null;
  email: string | null;
}

export interface PassAdjustmentResult {
  affected_djs: string[];
  affected_staff: AffectedStaffMember[];
}

export interface ShowResponse {
  id: number;
  event_name: string;
  genre: string[] | null;
  venue: VenueResponse;
  promoter_id?: number | null;
  show_date: string;
  show_time: string | null;
  show_start_date: string | null;
  on_air_description: string | null;
  caller_special_instructions: string | null;
  age_restriction: AgeRestriction;
  wheelchair_accessible: boolean;
  num_pass_pairs: number;
  promotions_contacts: PromotionsContact[];
  status: ShowStatus;
  passes: PassResponse[];
  attempts: ShowAttempt[];
  available_pair_count: number;
  available_staff_count: number;
  planned_close_date: string | null;
  planned_close_time: string | null;
  auto_close: boolean;
  co_announce: boolean;
  lottery_enabled: boolean;
  lottery_window_hours: number;
  dj_preassign_prohibition_days: number | null;
  published_at: string | null;
  pass_adjustment?: PassAdjustmentResult | null;
  bands: ShowBand[];
  is_mine: boolean;
}

export interface VenueShowSummary {
  id: number;
  name: string;
}

export interface ShowSummary {
  id: number;
  event_name: string;
  genre: string[] | null;
  venue: VenueShowSummary;
  show_date: string;
  show_time: string | null;
  show_start_date: string | null;
  caller_special_instructions: string | null;
  age_restriction: AgeRestriction;
  wheelchair_accessible: boolean;
  status: ShowStatus;
  num_pass_pairs: number;
  available_pair_count: number;
  available_staff_count: number;
  guest_hold_staff_count: number;
  co_announce: boolean;
  published_at: string | null;
  bands: ShowBand[];
  is_mine: boolean;
}

// Pass types
export type PassType = 'pair' | 'staff';
export type PassStatus = 'available' | 'given_away' | 'claimed';

export interface GiveawayData {
  recipient_name: string;
  recipient_phone: string;
  recipient_email?: string | null;
  given_away_by_dj: string;
}

export interface PassResponse {
  id: number;
  show_id: number;
  pass_type: PassType;
  status: PassStatus;

  // For pass pairs given away on-air
  recipient_name: string | null;
  recipient_phone: string | null;
  recipient_email: string | null;
  given_away_by_dj: string | null;
  given_away_at: string | null; // ISO datetime string

  // For staff passes claimed
  staff_id: number | null;
  staff_name: string | null;
  staff_phone: string | null;
  staff_email: string | null;
  claimed_at: string | null; // ISO datetime string

  // Staff +1 guest fields
  has_guest: boolean;
  guest_name: string | null;
  only_attend_with_guest: boolean;
  guest_of_pass_id: number | null;

  // For pre-assigned pairs
  preassigned_dj: string | null;
  preassigned_date: string | null; // ISO date string
  preassigned_specialty_show_id: number | null;
  preassigned_specialty_show_name: string | null;

  // Show details (for DJ history view)
  show_event_name: string | null;
  show_date: string | null;
  show_venue_name: string | null;
  show_status?: string | null;
}

export interface ClaimData {
  has_guest?: boolean;
  guest_name?: string | null;
  only_attend_with_guest?: boolean;
}

export interface PreAssignmentData {
  dj_name: string;
  assignment_date: string; // ISO date string
}

export interface SelfPreAssignmentData {
  assignment_date: string; // ISO date string
  specialty_show_id?: number | null;
  dj_name_override?: string | null;
}

export interface WinnerReleaseData {
  reason: string;
  releasing_name?: string;
  releasing_email?: string;
}

// User types
export type UserRole = 'promotions' | 'staff' | 'dj' | 'unauthorized';

export interface UserResponse {
  email: string | null;
  real_email?: string | null;
  role: UserRole;
  is_dj_network: boolean;
  is_station_office_network: boolean;
  is_staging?: boolean;
  impersonating_email?: string | null;
  is_impersonating_dj_network?: boolean;
  is_impersonating_station_office_network?: boolean;
  profile?: PromotionsStaffProfile | StaffProfile | null;
}

// Search types
export interface ShowListParams {
  date_from?: string;
  date_to?: string;
}

export interface ShowSearchParams extends ShowListParams {
  freetext?: string;
  venue_id?: number;
  artist?: string;
  genre?: string;
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
  errors: string[];
}

// Scheduled job status
export interface JobStatus {
  id: string;
  name: string;
  last_run_at: string | null;
  next_run_at: string | null;
}

export interface JobRunResult {
  success: boolean;
  message: string;
}

export interface AutoCloseScheduleItem {
  show_id: number;
  event_name: string;
  venue_name: string;
  planned_close_date: string;
  planned_close_time: string;
  show_status: string;
  schedule_status: 'scheduled' | 'past' | 'executed';
}

// Staging seed result types
export interface SeedResult {
  venues_added: number;
  venues_skipped: number;
  shows_added: number;
  shows_skipped: number;
  errors: string[];
}

// Winner eligibility check
export interface WinnerEligibility {
  eligible: boolean;
  last_win_show?: string;
  last_win_date?: string;
  days_since?: number;
  required_days?: number;
  reason?: string | null;
}

// Notification preferences
export interface NotificationPreferences {
  email_enabled: boolean;
}

// Impersonation
export interface ImpersonateRequest {
  email: string | null;
  is_dj_network: boolean;
  is_station_office_network?: boolean;
}

// Admin user list
export interface UserListItem {
  email: string;
  name: string;
  role: 'promotions' | 'staff';
}

// Audit log
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
