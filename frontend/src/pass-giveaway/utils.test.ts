import { describe, it, expect } from 'vitest';
import {
  addressHasStateOrZip,
  canDjEditWinner,
  canRecordDjGiveaways,
  compareVenueNames,
  canUsePassGiveawayAdmin,
  findRecentDjGiveaway,
  formatShowRating,
  isRecentShow,
  isStagingSublistDjStaff,
  showsPassGiveawayAdminLink,
  venueSortName,
} from './utils';
import { formatDateValue } from '../common/utils';
import type { UserResponse } from '../common/types';
import type { PassResponse } from './types';

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

describe('canDjEditWinner', () => {
  const now = new Date('2026-10-14T20:00:00Z');
  type EditablePass = Pick<PassResponse, 'status' | 'given_away_by_dj' | 'given_away_at'>;
  const pass = (overrides: Partial<EditablePass> = {}): EditablePass => ({
    status: 'given_away',
    given_away_by_dj: 'DJ Test',
    given_away_at: '2026-10-14T17:30:00Z',
    ...overrides,
  });
  const show = (overrides = {}) => ({
    status: 'published' as const,
    planned_close_date: null,
    planned_close_time: null,
    ...overrides,
  });

  it('lets the DJ who gave the passes away edit within 4 hours', () => {
    expect(canDjEditWinner(pass(), show(), 'DJ Test', now)).toBe(true);
  });

  it('ignores case and surrounding spaces in the DJ name', () => {
    expect(canDjEditWinner(pass(), show(), '  dj test ', now)).toBe(true);
  });

  it('refuses another DJ or a blank DJ name', () => {
    expect(canDjEditWinner(pass(), show(), 'DJ Other', now)).toBe(false);
    expect(canDjEditWinner(pass(), show(), ' ', now)).toBe(false);
  });

  it('refuses once 4 hours have passed', () => {
    const old = pass({ given_away_at: '2026-10-14T16:00:00Z' });
    expect(canDjEditWinner(old, show(), 'DJ Test', now)).toBe(false);
  });

  it('refuses passes that are not given away', () => {
    expect(canDjEditWinner(pass({ status: 'available' }), show(), 'DJ Test', now)).toBe(false);
  });

  it('refuses closed shows and shows past their planned close time', () => {
    expect(canDjEditWinner(pass(), show({ status: 'closed' }), 'DJ Test', now)).toBe(false);
    const closeAt = new Date(now.getTime() - 60 * 1000);
    const pastClose = show({
      planned_close_date: formatDateValue(closeAt),
      planned_close_time: `${String(closeAt.getHours()).padStart(2, '0')}:${String(closeAt.getMinutes()).padStart(2, '0')}:00`,
    });
    expect(canDjEditWinner(pass(), pastClose, 'DJ Test', now)).toBe(false);
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

describe('showsPassGiveawayAdminLink', () => {
  const admin: UserResponse = {
    email: 'head@test.com',
    role: 'staff',
    is_dj_network: false,
    is_station_office_network: false,
    is_site_admin: true,
  };

  it('links site admins and promotions admins to the Admin page', () => {
    expect(showsPassGiveawayAdminLink(admin)).toBe(true);
    expect(showsPassGiveawayAdminLink({ ...admin, is_site_admin: false, is_promotions_admin: true })).toBe(true);
    expect(showsPassGiveawayAdminLink({ ...admin, is_site_admin: false })).toBe(false);
    expect(showsPassGiveawayAdminLink(null)).toBe(false);
  });

  it('hides the link while impersonating, though the page still works', () => {
    const impersonating = { ...admin, is_staging: true, impersonating_email: 'staff@test.com' };
    expect(showsPassGiveawayAdminLink(impersonating)).toBe(false);
    expect(showsPassGiveawayAdminLink({ ...admin, is_impersonating_dj_network: true })).toBe(false);
    expect(canUsePassGiveawayAdmin(impersonating)).toBe(true);
  });
});

describe('canRecordDjGiveaways', () => {
  const user: UserResponse = {
    email: 'promo@test.com',
    role: 'promotions',
    is_dj_network: false,
    is_station_office_network: false,
  };

  it('records from the DJ studio network', () => {
    const studio: UserResponse = { ...user, email: null, role: 'dj', is_dj_network: true };
    expect(canRecordDjGiveaways(studio)).toBe(true);
  });

  it('records while impersonating the DJ studio network in staging', () => {
    const impersonating: UserResponse = { ...user, is_staging: true, is_dj_network: true, is_impersonating_dj_network: true };
    expect(canRecordDjGiveaways(impersonating)).toBe(true);
  });

  it('records for Sublist DJ staff in staging', () => {
    const sublistDj = { ...user, role: 'staff' as const, is_staging: true, profile: { is_sublist_dj: true } } as UserResponse;
    expect(canRecordDjGiveaways(sublistDj)).toBe(true);
  });

  it("doesn't record for promotions staff away from the studio, or nobody", () => {
    expect(canRecordDjGiveaways(user)).toBe(false);
    expect(canRecordDjGiveaways(null)).toBe(false);
  });
});

describe('formatShowRating', () => {
  const music = { venue: { venue_type: 'music' as const } };
  const cinema = { venue: { venue_type: 'movie_theater' as const } };

  it('shows the age restriction at a music venue', () => {
    expect(formatShowRating({ ...music, age_restriction: 'all_ages', movie_rating: null })).toBe(
      'All Ages',
    );
  });

  it('shows the movie rating at a movie theater', () => {
    expect(formatShowRating({ ...cinema, age_restriction: null, movie_rating: 'NR' })).toBe(
      'Not Rated',
    );
  });

  it("says Not set when the show lacks the field its venue uses", () => {
    expect(formatShowRating({ ...cinema, age_restriction: '21+', movie_rating: null })).toBe(
      'Not set',
    );
  });
});

describe('addressHasStateOrZip', () => {
  it.each([
    '2367 Shattuck Ave, Berkeley, CA 94704',
    '2367 Shattuck Ave, Berkeley, CA',
    '2367 Shattuck Ave, Berkeley CA',
    '2367 Shattuck Ave, Berkeley, ca',
    '2367 Shattuck Ave, Berkeley 94704',
    '2367 Shattuck Ave, Berkeley, CA 94704-1234',
    '2367 Shattuck Ave\nBerkeley, CA 94704',
    '2367 Shattuck Ave, Berkeley, CA 94704, USA',
    '2367 Shattuck Ave, Berkeley, C.A.',
    '2367 Shattuck Ave, Berkeley, California',
    '2367 Shattuck Ave Berkeley CA 94704',
    '2367 Shattuck Ave Berkeley CA',
    '1 Main St, Portland, OR',
  ])('flags %j', (address) => {
    expect(addressHasStateOrZip(address)).toBe(true);
  });

  it.each([
    '',
    '2367 Shattuck Ave, Berkeley',
    '12345 Main St',
    '12345 Main St, Oakland',
    '12345',
    '123 Washington St, Oakland',
    '123 California St',
    '100 Main St NE',
    '1 Ca St, Berkeley',
    '2367 Shattuck Ave, Side door around back in',
    '123 Sunset Blvd, LA',
  ])('does not flag %j', (address) => {
    expect(addressHasStateOrZip(address)).toBe(false);
  });
});

describe('venue name sorting', () => {
  it('drops a leading "The"', () => {
    expect(venueSortName('The Fox Theater')).toBe('Fox Theater');
    expect(venueSortName('the Chapel')).toBe('Chapel');
    expect(venueSortName('Theater Rhinoceros')).toBe('Theater Rhinoceros');
    expect(venueSortName('The')).toBe('The');
  });

  it('sorts "The" venues by the rest of their name', () => {
    const names = ['The Fox Theater', 'Greek Theatre', 'The Chapel', 'Bottom of the Hill', 'Theater Rhinoceros'];
    expect([...names].sort(compareVenueNames)).toEqual([
      'Bottom of the Hill',
      'The Chapel',
      'The Fox Theater',
      'Greek Theatre',
      'Theater Rhinoceros',
    ]);
  });
});
