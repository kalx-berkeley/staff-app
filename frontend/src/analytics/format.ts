import type { MetricFormat } from './types';
import { formatCalendarDate, formatPacific } from '../common/dateTime';

const number = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });

const formatDate = (iso: string) => {
  const [y, m] = iso.split('-').map(Number);
  if (!y || !m) return iso;
  return formatCalendarDate(iso, { year: 'numeric', month: 'short', day: 'numeric' });
};

const formatPhone = (digits: string) =>
  /^\d{10}$/.test(digits) ? `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}` : digits;

/** A metric value as text; "—" when there's no value. */
export function formatValue(value: unknown, format: MetricFormat): string {
  if (value === null || value === undefined || value === '') return '—';
  switch (format) {
    case 'percent':
      return `${Math.round(Number(value) * 100)}%`;
    case 'points': {
      const n = Math.round(Number(value));
      return `${n > 0 ? '+' : ''}${n} pts`;
    }
    case 'days':
      return `${number.format(Number(value))} days`;
    case 'hours': {
      const hours = Number(value);
      return hours >= 48 ? `${number.format(hours / 24)} days` : `${number.format(hours)} h`;
    }
    case 'number':
      return number.format(Number(value));
    case 'date':
      return formatDate(String(value));
    case 'datetime':
      return formatPacific(String(value));
    case 'phone':
      return formatPhone(String(value));
    default:
      return String(value);
  }
}

/** A value for sorting a table column: numbers as numbers, nulls last. */
export function sortValue(value: unknown): number | string | null {
  if (value === null || value === undefined || value === '') return null;
  if (typeof value === 'number') return value;
  return String(value).toLowerCase();
}
