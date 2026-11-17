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

/** Add days to a calendar date without interpreting it in the viewer's time zone. */
export function addCalendarDays(value: string, days: number): string {
  const [year, month, day] = value.slice(0, 10).split('-').map(Number);
  const date = new Date(Date.UTC(year, month - 1, day + days));
  const resultYear = date.getUTCFullYear();
  const resultMonth = String(date.getUTCMonth() + 1).padStart(2, '0');
  const resultDay = String(date.getUTCDate()).padStart(2, '0');
  return `${resultYear}-${resultMonth}-${resultDay}`;
}

function pacificOffsetAt(instantMs: number): number {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: PACIFIC_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(instantMs));
  const values = Object.fromEntries(parts.map(({ type, value }) => [type, value]));
  const localAsUtc = Date.UTC(
    Number(values.year),
    Number(values.month) - 1,
    Number(values.day),
    Number(values.hour),
    Number(values.minute),
    Number(values.second),
  );
  return localAsUtc - instantMs;
}

/** Convert a Pacific wall-clock date/time to an instant, accounting for DST. */
export function pacificWallTimeToInstant(date: string, time: string): Date {
  const [year, month, day] = date.slice(0, 10).split('-').map(Number);
  const match = /^(\d{2}):(\d{2})(?::\d{2})?$/.exec(time);
  if (!match) throw new RangeError(`Invalid Pacific wall-clock time: ${time}`);
  const hour = Number(match[1]);
  const minute = Number(match[2]);
  if (hour > 23 || minute > 59) throw new RangeError(`Invalid Pacific wall-clock time: ${time}`);

  const wallTimeMs = Date.UTC(year, month - 1, day, hour, minute);
  let guessMs = wallTimeMs;
  const candidates: number[] = [];
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const candidateMs = wallTimeMs - pacificOffsetAt(guessMs);
    candidates.push(candidateMs);
    if (candidateMs === guessMs) return new Date(candidateMs);
    guessMs = candidateMs;
  }

  // A wall time in the spring-forward gap does not exist. Move it forward to
  // the first corresponding time after the gap instead of exporting an invalid
  // instant. Real event times are normally outside this one-hour window.
  return new Date(Math.max(...candidates));
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
