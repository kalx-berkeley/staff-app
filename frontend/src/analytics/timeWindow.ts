/**
 * The time window an analytics page shows, kept in the URL's query string
 * (`?preset=last_quarter`, or `?from=2026-01-01&to=2026-03-31`) so a link
 * shows the same numbers to whoever opens it.
 */

export const PRESETS: { value: string; label: string }[] = [
  { value: 'last_30_days', label: 'Last 30 days' },
  { value: 'last_month', label: 'Last month' },
  { value: 'this_quarter', label: 'This quarter' },
  { value: 'last_quarter', label: 'Last quarter' },
  { value: 'this_year', label: 'This year' },
  { value: 'last_year', label: 'Last year' },
  { value: 'all_time', label: 'All time' },
];

export const DEFAULT_PRESET = 'last_30_days';

export const WINDOW_KEYS = ['preset', 'from', 'to'] as const;

export type WindowParams = { preset?: string; from?: string; to?: string };

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/** The window in *search*: a custom range when both dates are valid, else a preset. */
export function readWindow(search: URLSearchParams): WindowParams {
  const from = search.get('from');
  const to = search.get('to');
  if (from && to && ISO_DATE.test(from) && ISO_DATE.test(to)) {
    return { from, to };
  }
  const preset = search.get('preset');
  return { preset: PRESETS.some((p) => p.value === preset) ? preset! : DEFAULT_PRESET };
}

/** Only the window's part of *search*, as a query string ("?…" or ""), for links. */
export function windowQuery(search: URLSearchParams): string {
  const kept = new URLSearchParams();
  for (const key of WINDOW_KEYS) {
    const value = search.get(key);
    if (value) kept.set(key, value);
  }
  const query = kept.toString();
  return query ? `?${query}` : '';
}
