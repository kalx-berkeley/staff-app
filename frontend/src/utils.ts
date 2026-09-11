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
