import { describe, it, expect } from 'vitest';
import { formatLeave, isOnLeave, isStagingEnvironment, leaveCoversShow } from './utils';

describe('isStagingEnvironment', () => {
  it('detects the staff staging hostname', () => {
    expect(isStagingEnvironment('staff.stage.kalx.berkeley.edu')).toBe(true);
  });

  it('detects a bare stage subdomain', () => {
    expect(isStagingEnvironment('stage.kalx.berkeley.edu')).toBe(true);
  });

  it('does not flag production', () => {
    expect(isStagingEnvironment('staff.kalx.berkeley.edu')).toBe(false);
  });

  it('does not flag unrelated labels containing "stage"', () => {
    expect(isStagingEnvironment('backstage.kalx.berkeley.edu')).toBe(false);
  });

  it('does not flag localhost', () => {
    expect(isStagingEnvironment('localhost')).toBe(false);
  });
});

describe('leave of absence helpers', () => {
  it('treats both ends as inclusive and handles one-sided leave', () => {
    const leave = { loa_start: '2030-03-01', loa_end: '2030-03-31' };
    expect(isOnLeave(leave, '2030-02-28')).toBe(false);
    expect(isOnLeave(leave, '2030-03-01')).toBe(true);
    expect(isOnLeave(leave, '2030-03-31')).toBe(true);
    expect(isOnLeave(leave, '2030-04-01')).toBe(false);
    expect(isOnLeave({ loa_start: '2030-03-01', loa_end: null }, '2099-01-01')).toBe(true);
    expect(isOnLeave({ loa_start: null, loa_end: '2030-03-31' }, '2000-01-01')).toBe(true);
    expect(isOnLeave({ loa_start: null, loa_end: null }, '2030-03-01')).toBe(false);
    expect(isOnLeave(null, '2030-03-01')).toBe(false);
  });

  it('covers a show only when every day of it falls within the leave', () => {
    const leave = { loa_start: '2030-06-01', loa_end: '2030-06-15' };
    expect(leaveCoversShow(leave, { show_date: '2030-06-15' })).toBe(true);
    expect(leaveCoversShow(leave, { show_start_date: '2030-06-14', show_date: '2030-06-16' })).toBe(false);
  });

  it('formats the range like the backend', () => {
    expect(formatLeave({ loa_start: '2030-03-01', loa_end: '2030-06-01' })).toBe('Mar 1, 2030 – Jun 1, 2030');
    expect(formatLeave({ loa_start: '2030-03-01', loa_end: null })).toBe('from Mar 1, 2030');
    expect(formatLeave({ loa_start: null, loa_end: '2030-06-01' })).toBe('until Jun 1, 2030');
  });
});
