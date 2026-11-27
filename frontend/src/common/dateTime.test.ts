import { describe, expect, it } from 'vitest';
import {
  addCalendarDays,
  calendarDaysBetween,
  formatCalendarDate,
  formatCalendarDateRange,
  formatPacific,
  formatPacificTime,
  pacificDateString,
  parseInstant,
} from './dateTime';

describe('parseInstant', () => {
  it('reads a timestamp without a zone as UTC', () => {
    expect(parseInstant('2026-11-13T03:15:42.123456').toISOString()).toBe('2026-11-13T03:15:42.123Z');
  });

  it('keeps a timestamp that has a zone', () => {
    expect(parseInstant('2026-11-13T03:15:00-08:00').toISOString()).toBe('2026-11-13T11:15:00.000Z');
    expect(parseInstant('2026-11-13T03:15:00Z').toISOString()).toBe('2026-11-13T03:15:00.000Z');
  });
});

describe('formatPacific', () => {
  it('shows a UTC timestamp in Pacific time, to the minute', () => {
    // 03:15 UTC on Nov 13 is 7:15pm PST on Nov 12
    expect(formatPacific('2026-11-13T03:15:42.123456')).toBe('Nov 12, 2026, 7:15 PM');
  });

  it('uses daylight saving time in summer', () => {
    expect(formatPacific('2026-07-04T19:00:00Z', { hour: 'numeric' })).toBe('12:00 PM');
  });

  it('formats the time alone', () => {
    expect(formatPacificTime('2026-11-13T03:15:00Z')).toBe('7:15pm');
  });
});

describe('pacificDateString', () => {
  it('is the Pacific calendar date, not the UTC one', () => {
    expect(pacificDateString('2026-11-13T03:15:00Z')).toBe('2026-11-12');
  });
});

describe('addCalendarDays', () => {
  it('adds and subtracts days across months and years', () => {
    expect(addCalendarDays('2026-11-20', 1)).toBe('2026-11-21');
    expect(addCalendarDays('2026-11-30', 1)).toBe('2026-12-01');
    expect(addCalendarDays('2026-12-31', 1)).toBe('2027-01-01');
    expect(addCalendarDays('2026-03-01', -1)).toBe('2026-02-28');
  });

  it('is not thrown off by daylight saving time', () => {
    expect(addCalendarDays('2026-11-01', 1)).toBe('2026-11-02');
    expect(addCalendarDays('2026-03-08', -1)).toBe('2026-03-07');
  });
});

describe('calendarDaysBetween', () => {
  it('counts days forwards and backwards', () => {
    expect(calendarDaysBetween('2026-11-20', '2026-11-21')).toBe(1);
    expect(calendarDaysBetween('2026-11-21', '2026-11-19')).toBe(-2);
    expect(calendarDaysBetween('2026-11-20', '2026-11-20')).toBe(0);
  });
});

describe('formatCalendarDate', () => {
  it('formats a calendar date as that same day', () => {
    expect(formatCalendarDate('2026-11-12')).toBe('Thu, Nov 12, 2026');
  });

  it('formats a month', () => {
    expect(formatCalendarDate('2026-11', { month: 'long', year: 'numeric' })).toBe('November 2026');
  });

  it('formats a range', () => {
    expect(formatCalendarDateRange('2026-11-12', '2026-11-14')).toBe('Nov 12 – Nov 14, 2026');
  });
});
