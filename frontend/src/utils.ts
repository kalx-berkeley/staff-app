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
