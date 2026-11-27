/**
 * Helpers for venues that give staff passes for a different date than the
 * on-air pass pairs, whose new shows are created as two shows. See
 * docs/pass-giveaway/specs/staff-passes-another-date/plan.md.
 */

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
