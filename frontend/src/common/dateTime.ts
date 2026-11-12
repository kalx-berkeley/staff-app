// Every date and time the app shows goes through this file, so that they're
// all in Pacific time whatever the viewer's own time zone.
// `dateTime.guard.test.ts` fails if any other file formats dates itself.
//
// There are two kinds of value:
// - An instant (an API timestamp such as "2026-11-12T23:45:00Z"): use
//   `formatPacific`. A timestamp without a zone is UTC, which is how the
//   database stores them.
// - A calendar date ("2026-11-12", such as a show date) or a month
//   ("2026-11"): use `formatCalendarDate`. It has no time zone, so it's
//   formatted as the same day for everyone.

export const PACIFIC_TIME_ZONE = 'America/Los_Angeles';

const HAS_ZONE = /(Z|[+-]\d\d:?\d\d)$/i;

/** An API timestamp as a Date. One without a zone is taken as UTC. */
export function parseInstant(value: string | Date): Date {
  if (value instanceof Date) return value;
  return new Date(HAS_ZONE.test(value) || !value.includes('T') ? value : `${value}Z`);
}

/** "Nov 12, 2026, 3:45 PM": the default for `formatPacific`. */
export const DATE_TIME: Intl.DateTimeFormatOptions = {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
};

/**
 * An instant in Pacific time. Pass `options` to choose the parts shown; give
 * `hour` without `minute` and it shows minutes too, never seconds.
 */
export function formatPacific(
  value: string | Date,
  options: Intl.DateTimeFormatOptions = DATE_TIME,
): string {
  const parts = options.hour && !options.minute ? { ...options, minute: '2-digit' as const } : options;
  return parseInstant(value).toLocaleString('en-US', { ...parts, timeZone: PACIFIC_TIME_ZONE });
}

/** An instant's time of day in Pacific time, as "3:45pm". */
export function formatPacificTime(value: string | Date): string {
  return formatPacific(value, { hour: 'numeric', minute: '2-digit' }).replace(' ', '').toLowerCase();
}

/** An instant's calendar date in Pacific time, as "YYYY-MM-DD". */
export function pacificDateString(value: string | Date = new Date()): string {
  return parseInstant(value).toLocaleDateString('en-CA', { timeZone: PACIFIC_TIME_ZONE });
}

/** "Wed, Nov 12, 2026": the default for `formatCalendarDate`. */
export const CALENDAR_DATE: Intl.DateTimeFormatOptions = {
  weekday: 'short',
  year: 'numeric',
  month: 'short',
  day: 'numeric',
};

/**
 * A calendar date ("2026-11-12") or month ("2026-11"), the same day for every
 * viewer. A month is shown as its first day, so pass options without `day`.
 */
export function formatCalendarDate(
  value: string,
  options: Intl.DateTimeFormatOptions = CALENDAR_DATE,
): string {
  const [year, month, day] = value.slice(0, 10).split('-').map(Number);
  return new Date(Date.UTC(year, month - 1, day || 1)).toLocaleDateString('en-US', {
    ...options,
    timeZone: 'UTC',
  });
}

/** Two calendar dates as "Nov 12 – Nov 14, 2026". */
export function formatCalendarDateRange(start: string, end: string): string {
  const startFmt = formatCalendarDate(start, { month: 'short', day: 'numeric' });
  const endFmt = formatCalendarDate(end, { month: 'short', day: 'numeric', year: 'numeric' });
  return `${startFmt} – ${endFmt}`;
}
