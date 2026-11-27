import { describe, expect, it } from 'vitest';
import { describeDayOffset, formatClockTime } from './splitShow';

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
