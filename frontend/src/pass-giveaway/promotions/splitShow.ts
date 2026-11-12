/**
 * Helpers for venues that give staff passes for a different date than the
 * on-air pass pairs, whose new shows are created as two shows. See
 * docs/pass-giveaway/specs/staff-passes-another-date/plan.md.
 */

const DAY_MS = 24 * 60 * 60 * 1000;

const toUtcMs = (date: string) => {
  const [year, month, day] = date.split('-').map(Number);
  return Date.UTC(year, month - 1, day);
};

/** The calendar date ("YYYY-MM-DD") `days` days after `date` (before, if negative). */
export function addDays(date: string, days: number): string {
  const d = new Date(toUtcMs(date) + days * DAY_MS);
  return [
    d.getUTCFullYear(),
    String(d.getUTCMonth() + 1).padStart(2, '0'),
    String(d.getUTCDate()).padStart(2, '0'),
  ].join('-');
}

/** How many days `to` is after `from` (negative if before). */
export function daysBetween(from: string, to: string): number {
  return Math.round((toUtcMs(to) - toUtcMs(from)) / DAY_MS);
}

/** "20:00" as "8:00 PM". */
export function formatClockTime(time: string): string {
  const [hours, minutes] = time.split(':').map(Number);
  const suffix = hours >= 12 ? 'PM' : 'AM';
  const hour12 = hours % 12 === 0 ? 12 : hours % 12;
  return `${hour12}:${String(minutes).padStart(2, '0')} ${suffix}`;
}

/** "1 day after", "2 days before" */
export function describeDayOffset(days: number): string {
  const n = Math.abs(days);
  return `${n} day${n === 1 ? '' : 's'} ${days > 0 ? 'after' : 'before'}`;
}
