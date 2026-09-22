import { describe, it, expect } from 'vitest';
import { isStagingEnvironment, isStagingSublistDjStaff } from './utils';
import type { UserResponse } from './types';

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

describe('isStagingSublistDjStaff', () => {
  const baseUser: UserResponse = {
    email: 'dj@test.com',
    role: 'staff',
    is_dj_network: false,
    is_station_office_network: false,
    is_staging: true,
    profile: { name: 'DJ Test', phone: '555-0000', dj_name: 'DJ Test', is_sublist_dj: true },
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
      profile: { name: 'Staffer', phone: '555-0000', dj_name: null, is_sublist_dj: false },
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
