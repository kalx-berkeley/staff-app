import { describe, it, expect } from 'vitest';
import type { DirectoryEntry } from '../../types';
import { digitsOnly, initials, matchesSearch } from './directorySearch';

const entry: DirectoryEntry = {
  id: 1,
  name: 'Jane Doe',
  pronouns: 'she/her',
  email: 'jane@example.com',
  phone: '(510) 642-1111',
  dj_name: 'DJ Janey',
  spinitron_ids: [42],
  departments: ['Music', 'News'],
  statuses: ['Active', 'Paid Staff'],
  titles_and_roles: 'Music Director\nOffice hours: Tue 2-4',
  photo_version: null,
};

describe('matchesSearch', () => {
  it('matches everything for a blank query', () => {
    expect(matchesSearch(entry, '')).toBe(true);
    expect(matchesSearch(entry, '   ')).toBe(true);
  });

  it.each([
    ['jane'],
    ['DOE'],
    ['janey'],
    ['example.com'],
    ['news'],
    ['paid staff'],
    ['office hours'],
    ['music director'],
  ])('matches %s in a searched field', (query) => {
    expect(matchesSearch(entry, query)).toBe(true);
  });

  it('requires every term to match', () => {
    expect(matchesSearch(entry, 'jane sports')).toBe(false);
  });

  it('does not search pronouns', () => {
    expect(matchesSearch(entry, 'she/her')).toBe(false);
  });

  it.each([['510-642'], ['5106421111'], ['(510) 642'], ['642.1111']])(
    'matches the phone number %s by its digits',
    (query) => {
      expect(matchesSearch(entry, query)).toBe(true);
    },
  );

  it('does not match phone digits that are not in the number', () => {
    expect(matchesSearch(entry, '415-555')).toBe(false);
  });
});

describe('digitsOnly', () => {
  it('drops everything but digits', () => {
    expect(digitsOnly('+1 (510) 642-1111')).toBe('15106421111');
  });
});

describe('initials', () => {
  it('uses the first and last words', () => {
    expect(initials('Jane Q. Doe')).toBe('JD');
    expect(initials('prince')).toBe('P');
    expect(initials('')).toBe('?');
  });
});
