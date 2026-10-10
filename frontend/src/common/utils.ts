export function formatPhone(phone: string | null | undefined): string {
  if (!phone) return '—';
  const digits = phone.replace(/\D/g, '');
  if (digits.length === 10) {
    return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`;
  }
  return phone;
}

// Matches "stage" as a full hostname label (e.g. staff.stage.example.org or
// stage.example.org) without matching unrelated labels like "backstage".
export function isStagingEnvironment(hostname: string = window.location.hostname): boolean {
  return /(^|\.)stage\./.test(hostname);
}

/**
 * Parse a `YYYY-MM-DD` string into a local-midnight Date, matching how the
 * rest of the app parses date-only strings (avoids UTC-vs-local off-by-one).
 */
export function parseDateValue(value: string): Date | undefined {
  if (!value) return undefined;
  const [y, m, d] = value.split('-').map(Number);
  if (!y || !m || !d) return undefined;
  return new Date(y, m - 1, d);
}

/** Format a local Date back into the `YYYY-MM-DD` string the rest of the app uses. */
export function formatDateValue(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

/** Format a `YYYY-MM-DD` string for display as free-typeable text: `MM/DD/YYYY`. */
export function formatDateForDisplay(value: string): string {
  const date = parseDateValue(value);
  if (!date) return '';
  return `${String(date.getMonth() + 1).padStart(2, '0')}/${String(date.getDate()).padStart(2, '0')}/${date.getFullYear()}`;
}

/**
 * Parse free-typed date text into a `YYYY-MM-DD` string.
 *
 * Accepts `M/D/YYYY` (the display format) and `YYYY-MM-DD` (the value
 * format, e.g. pasted from elsewhere in the app), with 1- or 2-digit month/day.
 * Returns `''` for blank input, or `null` when the text isn't a real date
 * (bad format, or a calendar date that doesn't exist, like Feb 30).
 */
export function parseFreeformDate(text: string): string | null {
  const trimmed = text.trim();
  if (!trimmed) return '';

  const slash = trimmed.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  const iso = trimmed.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  let y: number, mo: number, d: number;
  if (slash) {
    mo = Number(slash[1]);
    d = Number(slash[2]);
    y = Number(slash[3]);
  } else if (iso) {
    y = Number(iso[1]);
    mo = Number(iso[2]);
    d = Number(iso[3]);
  } else {
    return null;
  }

  if (mo < 1 || mo > 12 || d < 1 || d > 31) return null;
  const date = new Date(y, mo - 1, d);
  if (date.getFullYear() !== y || date.getMonth() !== mo - 1 || date.getDate() !== d) {
    return null;
  }
  return formatDateValue(date);
}

/** Leave-of-absence dates as `YYYY-MM-DD` strings; either may be null for a one-sided leave. */
export interface LeaveDates {
  loa_start?: string | null;
  loa_end?: string | null;
}

/**
 * Whether `day` (`YYYY-MM-DD`) falls within a leave of absence, inclusive.
 * A start alone is open-ended; an end alone means on leave until then.
 */
export function isOnLeave(leave: LeaveDates | null | undefined, day: string): boolean {
  if (!leave || (!leave.loa_start && !leave.loa_end)) return false;
  if (leave.loa_start && day < leave.loa_start) return false;
  if (leave.loa_end && day > leave.loa_end) return false;
  return true;
}

/** Whether a leave covers every day of a show (`show_start_date` through `show_date`). */
export function leaveCoversShow(
  leave: LeaveDates | null | undefined,
  show: { show_date: string; show_start_date?: string | null },
): boolean {
  return isOnLeave(leave, show.show_start_date ?? show.show_date) && isOnLeave(leave, show.show_date);
}

function formatLeaveDate(value: string): string {
  return parseDateValue(value)!.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

/** Describe leave dates the way the backend does, e.g. "Mar 1, 2027 – Jun 1, 2027" or "from Mar 1, 2027". */
export function formatLeave(leave: LeaveDates): string {
  if (leave.loa_start && leave.loa_end) {
    return `${formatLeaveDate(leave.loa_start)} – ${formatLeaveDate(leave.loa_end)}`;
  }
  if (leave.loa_start) return `from ${formatLeaveDate(leave.loa_start)}`;
  return leave.loa_end ? `until ${formatLeaveDate(leave.loa_end)}` : '';
}
