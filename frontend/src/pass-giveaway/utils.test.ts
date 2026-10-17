import { describe, it, expect } from 'vitest';
import { findRecentDjGiveaway, isRecentShow, isStagingSublistDjStaff } from './utils';
import { formatDateValue } from '../common/utils';
import type { UserResponse } from '../common/types';

describe('isStagingSublistDjStaff', () => {
  const baseUser: UserResponse = {
    email: 'dj@test.com',
    role: 'staff',
    is_dj_network: false,
    is_station_office_network: false,
    is_staging: true,
    profile: { id: 1, name: 'DJ Test', phone: '555-0000', dj_name: 'DJ Test', is_sublist_dj: true },
  };

  it('allows a staff member with Sublist DJ status in staging', () => {
    expect(isStagingSublistDjStaff(baseUser)).toBe(true);
  });

  it('denies outside staging', () => {
    expect(isStagingSublistDjStaff({ ...baseUser, is_staging: false })).toBe(false);
  });

  it('denies a staff member without Sublist DJ status', () => {
    expect(isStagingSublistDjStaff({
      ...baseUser,
      profile: { id: 1, name: 'Staffer', phone: '555-0000', dj_name: null, is_sublist_dj: false },
    })).toBe(false);
  });

  it('denies non-staff roles even if is_sublist_dj is set', () => {
    expect(isStagingSublistDjStaff({ ...baseUser, role: 'promotions' })).toBe(false);
  });

  it('denies a missing user', () => {
    expect(isStagingSublistDjStaff(null)).toBe(false);
    expect(isStagingSublistDjStaff(undefined)).toBe(false);
  });
});

describe('findRecentDjGiveaway', () => {
  const now = new Date('2026-10-14T20:00:00Z');
  const pass = (given_away_by_dj: string | null, given_away_at: string | null) => ({
    given_away_by_dj,
    given_away_at,
  });

  it('finds a giveaway by the same DJ within the last 4 hours', () => {
    const passes = [pass('DJ Test', '2026-10-14T17:30:00Z')];
    expect(findRecentDjGiveaway(passes, 'DJ Test', now)).toBe(passes[0]);
  });

  it('ignores case and surrounding spaces in the DJ name', () => {
    const passes = [pass('DJ Test', '2026-10-14T19:00:00Z')];
    expect(findRecentDjGiveaway(passes, '  dj test ', now)).toBe(passes[0]);
  });

  it('ignores giveaways older than 4 hours', () => {
    const passes = [pass('DJ Test', '2026-10-14T15:59:00Z')];
    expect(findRecentDjGiveaway(passes, 'DJ Test', now)).toBeUndefined();
  });

  it('ignores giveaways by other DJs', () => {
    const passes = [pass('DJ Other', '2026-10-14T19:00:00Z')];
    expect(findRecentDjGiveaway(passes, 'DJ Test', now)).toBeUndefined();
  });

  it('finds nothing when no DJ name is entered', () => {
    const passes = [pass(null, null), pass('DJ Test', '2026-10-14T19:00:00Z')];
    expect(findRecentDjGiveaway(passes, ' ', now)).toBeUndefined();
  });
});

describe('isRecentShow', () => {
  const daysFromToday = (days: number) => {
    const d = new Date();
    d.setDate(d.getDate() + days);
    return formatDateValue(d);
  };

  it('keeps upcoming shows and shows up to 3 days ago', () => {
    expect(isRecentShow(daysFromToday(5))).toBe(true);
    expect(isRecentShow(daysFromToday(0))).toBe(true);
    expect(isRecentShow(daysFromToday(-3))).toBe(true);
  });

  it('drops shows more than 3 days ago', () => {
    expect(isRecentShow(daysFromToday(-4))).toBe(false);
  });

  it('keeps passes with no show date', () => {
    expect(isRecentShow(null)).toBe(true);
  });
});
