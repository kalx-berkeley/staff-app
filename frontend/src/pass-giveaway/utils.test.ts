import { describe, it, expect } from 'vitest';
import { isStagingSublistDjStaff } from './utils';
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
