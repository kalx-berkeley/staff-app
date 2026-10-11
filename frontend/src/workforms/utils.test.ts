import { describe, expect, it } from 'vitest';
import {
  errorMessage,
  formatHours,
  formatMonth,
  groupEntries,
  hoursProblem,
  hoursShort,
  monthBounds,
  nextPendingIndex,
  statusLabel,
} from './utils';

describe('formatMonth and monthBounds', () => {
  it('names the month', () => {
    expect(formatMonth('2026-10')).toBe('October 2026');
  });

  it('gives the first and last days', () => {
    expect(monthBounds('2026-02')).toEqual({ min: '2026-02-01', max: '2026-02-28' });
    expect(monthBounds('2028-02').max).toBe('2028-02-29');
    expect(monthBounds('2026-10').max).toBe('2026-10-31');
  });
});

describe('hours', () => {
  it('formats without trailing zeros', () => {
    expect(formatHours(2)).toBe('2');
    expect(formatHours(1.5)).toBe('1.5');
    expect(formatHours(0.25)).toBe('0.25');
  });

  it('accepts positive quarter hours only', () => {
    expect(hoursProblem('1.25')).toBeNull();
    expect(hoursProblem('300')).toBeNull();
    expect(hoursProblem('')).not.toBeNull();
    expect(hoursProblem('0')).not.toBeNull();
    expect(hoursProblem('-1')).not.toBeNull();
    expect(hoursProblem('1.1')).not.toBeNull();
    expect(hoursProblem('abc')).not.toBeNull();
  });
});

describe('groupEntries', () => {
  it('groups by department with dated entries first, by date', () => {
    const groups = groupEntries([
      { id: 1, department: 'Music', work_date: null },
      { id: 2, department: 'Music', work_date: '2026-10-17' },
      { id: 3, department: 'Promotions', work_date: null },
      { id: 4, department: 'Music', work_date: '2026-10-03' },
    ]);
    expect([...groups.keys()]).toEqual(['Music', 'Promotions']);
    expect(groups.get('Music')!.map((e) => e.id)).toEqual([4, 2, 1]);
  });
});

describe('nextPendingIndex', () => {
  it('finds the next undecided item, wrapping around', () => {
    const items = [{ decision: null }, { decision: 'Approved' as const }, { decision: null }];
    expect(nextPendingIndex(items, 0)).toBe(2);
    expect(nextPendingIndex(items, 2)).toBe(0);
    expect(nextPendingIndex([{ decision: 'Denied' as const }], 0)).toBeNull();
  });
});

describe('errorMessage', () => {
  it('reads API error details', () => {
    expect(errorMessage({ detail: 'Nope' })).toBe('Nope');
    expect(errorMessage({ detail: [{ loc: [], msg: 'bad', type: 'x' }] })).toBe('bad');
    expect(errorMessage(new Error('Network'))).toBe('Network');
  });
});

describe('statusLabel', () => {
  it('says partly reviewed until every department has decided', () => {
    const approved = { hours: 2, description: null, decision: 'Approved' as const };
    const pending = { hours: 1, description: null, decision: null };
    expect(statusLabel({ status: 'locked', results: { A: approved, B: pending } })).toBe(
      'Partly reviewed'
    );
    expect(statusLabel({ status: 'locked', results: { A: approved } })).toBe('Reviewed');
    expect(statusLabel({ status: 'draft', results: {} })).toBe('Not submitted');
  });
});

describe('hoursShort', () => {
  it('counts the hours still needed to reach 6', () => {
    expect(hoursShort(0)).toBe(6);
    expect(hoursShort(4.75)).toBe(1.25);
  });

  it('is 0 at or over 6 hours', () => {
    expect(hoursShort(6)).toBe(0);
    expect(hoursShort(9.5)).toBe(0);
  });
});
