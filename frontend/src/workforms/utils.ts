import type { APIError } from '../common/types';
import type { Entry, ReviewItem, WorkformStatus, WorkformSummary } from './types';

const STATUS_LABELS: Record<WorkformStatus, string> = {
  not_started: 'Not started',
  draft: 'Not submitted',
  submitted: 'Submitted',
  locked: 'Reviewed',
};

/** A workform's status in a few words; "Partly reviewed" while some departments haven't decided. */
export function statusLabel(workform: Pick<WorkformSummary, 'status' | 'results'>): string {
  if (
    workform.status === 'locked' &&
    Object.values(workform.results).some((r) => r.hours !== null && !r.decision)
  ) {
    return 'Partly reviewed';
  }
  return STATUS_LABELS[workform.status];
}

/** "2026-10" → "October 2026". */
export function formatMonth(month: string): string {
  const [year, m] = month.split('-').map(Number);
  return new Date(year, m - 1, 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
}

/** The first and last days of a "YYYY-MM" month, as "YYYY-MM-DD", for a date input's min and max. */
export function monthBounds(month: string): { min: string; max: string } {
  const [year, m] = month.split('-').map(Number);
  const last = new Date(year, m, 0).getDate();
  return { min: `${month}-01`, max: `${month}-${String(last).padStart(2, '0')}` };
}

/** Hours without trailing zeros: 2, 1.5, 0.25. */
export function formatHours(hours: number): string {
  return String(Number(hours.toFixed(2)));
}

/** Why an hours value can't be saved, or null if it's fine: more than 0, in quarter hours. */
export function hoursProblem(value: string): string | null {
  const hours = Number(value);
  if (value.trim() === '' || Number.isNaN(hours)) return 'Enter the number of hours';
  if (hours <= 0) return 'Hours must be more than 0';
  if (Math.abs(hours * 4 - Math.round(hours * 4)) > 1e-9)
    return 'Use quarter hours, like 1.25 or 1.5';
  return null;
}

/** "2026-10-03" → "Oct 3". */
export function formatDay(value: string): string {
  const [year, m, d] = value.split('-').map(Number);
  return new Date(year, m - 1, d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/** Entries grouped by department, each group's dated entries first by date, as the backend combines them. */
export function groupEntries<T extends Pick<Entry, 'department' | 'work_date'> & { id?: number }>(
  entries: T[]
): Map<string, T[]> {
  const sorted = [...entries].sort((a, b) => {
    if (!a.work_date !== !b.work_date) return a.work_date ? -1 : 1;
    if (a.work_date && b.work_date && a.work_date !== b.work_date) {
      return a.work_date < b.work_date ? -1 : 1;
    }
    return (a.id ?? 0) - (b.id ?? 0);
  });
  const groups = new Map<string, T[]>();
  for (const entry of sorted) {
    groups.set(entry.department, [...(groups.get(entry.department) ?? []), entry]);
  }
  return groups;
}

export function totalHours(entries: { hours: number }[]): number {
  return entries.reduce((sum, e) => sum + e.hours, 0);
}

/** The next item without a decision after *index*, wrapping around; null if all are decided. */
export function nextPendingIndex(
  items: Pick<ReviewItem, 'decision'>[],
  index: number
): number | null {
  for (let step = 1; step <= items.length; step++) {
    const i = (index + step) % items.length;
    if (!items[i].decision) return i;
  }
  return null;
}

/** A message for an error thrown by the API helpers. */
export function errorMessage(error: unknown): string {
  const detail = (error as APIError | undefined)?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length) return detail.map((d) => d.msg).join('; ');
  if (error instanceof Error) return error.message;
  return 'Something went wrong. Please try again.';
}
