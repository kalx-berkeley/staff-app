import { describe, it, expect } from 'vitest';
import { isStagingEnvironment } from './utils';

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
