import { describe, expect, it } from 'vitest';
import { addDays, daysBetween, describeDayOffset, formatClockTime } from './splitShow';

describe('addDays', () => {
  it('adds and subtracts days across months and years', () => {
    expect(addDays('2026-11-20', 1)).toBe('2026-11-21');
    expect(addDays('2026-11-30', 1)).toBe('2026-12-01');
    expect(addDays('2027-01-01', -1)).toBe('2026-12-31');
  });

  it('is not thrown off by daylight saving time', () => {
    expect(addDays('2026-11-01', 1)).toBe('2026-11-02');
    expect(addDays('2026-03-08', -1)).toBe('2026-03-07');
  });
});

describe('daysBetween', () => {
  it('counts days forwards and backwards', () => {
    expect(daysBetween('2026-11-20', '2026-11-21')).toBe(1);
    expect(daysBetween('2026-11-21', '2026-11-19')).toBe(-2);
    expect(daysBetween('2026-11-20', '2026-11-20')).toBe(0);
  });
});

describe('formatClockTime', () => {
  it('formats 24-hour times as 12-hour times', () => {
    expect(formatClockTime('20:00')).toBe('8:00 PM');
    expect(formatClockTime('00:30')).toBe('12:30 AM');
    expect(formatClockTime('12:05')).toBe('12:05 PM');
  });
});

describe('describeDayOffset', () => {
  it('says how many days after or before', () => {
    expect(describeDayOffset(1)).toBe('1 day after');
    expect(describeDayOffset(-2)).toBe('2 days before');
  });
});
