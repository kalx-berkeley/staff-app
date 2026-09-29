import type { DirectoryEntry } from '../../types';

/** The digits in a string, e.g. "(510) 642-1111" → "5106421111". */
export function digitsOnly(value: string): string {
  return value.replace(/\D/g, '');
}

/**
 * Whether a directory entry matches a search query.
 *
 * Every whitespace-separated term must match somewhere (case-insensitively)
 * in the name, DJ name, email, departments, statuses, or Titles and Roles.
 * A term made up of digits and phone punctuation also matches the phone
 * number by its digits alone, so "510-642" finds "(510) 642-1111".
 */
export function matchesSearch(entry: DirectoryEntry, query: string): boolean {
  const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (terms.length === 0) return true;

  const text = [
    entry.name,
    entry.dj_name ?? '',
    entry.email,
    ...entry.departments,
    ...entry.statuses,
    entry.titles_and_roles ?? '',
  ]
    .join('\n')
    .toLowerCase();
  const phoneDigits = digitsOnly(entry.phone);

  return terms.every((term) => {
    if (text.includes(term)) return true;
    const termDigits = digitsOnly(term);
    return /^[\d\s().+-]+$/.test(term) && termDigits !== '' && phoneDigits.includes(termDigits);
  });
}

/** Up to two initials for a name, e.g. "Jane Q. Doe" → "JD". */
export function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return '?';
  const first = words[0][0];
  const last = words.length > 1 ? words[words.length - 1][0] : '';
  return (first + last).toUpperCase();
}

/** Spinitron's public page for a DJ persona. */
export function spinitronUrl(personaId: number): string {
  return `https://spinitron.com/KALX/dj/${personaId}/`;
}
