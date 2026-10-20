// Formatting for the profile page.

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

/** "2026-09" → "September 2026". */
export function formatMonthKey(month: string): string {
  const [year, number] = month.split('-').map(Number);
  return `${MONTHS[number - 1]} ${year}`;
}

/** "2026-09-30" → "Sep 30, 2026". */
export function formatDate(value: string): string {
  const [year, month, day] = value.split('-').map(Number);
  return new Date(year, month - 1, day).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

/** An ISO timestamp as "Sep 30, 2026, 3:30 AM" in the viewer's time zone. */
export function formatDateTime(value: string): string {
  return new Date(value).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

/** 135 → "2 h 15 min", 60 → "1 h", 45 → "45 min". */
export function formatMinutes(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours && rest) return `${hours} h ${rest} min`;
  return hours ? `${hours} h` : `${rest} min`;
}

/** 6 → "6", 4.5 → "4.5". */
export function formatHours(hours: number): string {
  return String(Math.round(hours * 100) / 100);
}

/**
 * A URL in /workforms/ for one month of someone's workform: their own month
 * page, or (for a site admin) the read-only view of someone else's.
 */
export function workformMonthUrl(month: string, staffId: number | null): string {
  return staffId === null
    ? `/workforms/month/${month}`
    : `/workforms/staff/${staffId}/month/${month}`;
}

/** Whether `value` looks like a link rather than a name being typed. */
export function looksLikeUrl(value: string): boolean {
  return /^https?:\/\//i.test(value.trim());
}
