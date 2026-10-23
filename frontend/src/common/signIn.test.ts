import { describe, it, expect } from 'vitest';
import { isSignInPath, signInTarget, signInUrl } from './signIn';

describe('signInUrl', () => {
  it('should round-trip the path through signInTarget', () => {
    const path = '/pass-giveaway/dj/winner-search?phone=510';
    const url = new URL(signInUrl(path), 'https://staff.example.com');

    expect(isSignInPath(url.pathname)).toBe(true);
    expect(signInTarget(url.search)).toBe(path);
  });
});

describe('signInTarget', () => {
  it('should return a path on this site', () => {
    expect(signInTarget('?next=%2Fpass-giveaway%2Fstaff%2Fshows')).toBe(
      '/pass-giveaway/staff/shows',
    );
  });

  it('should keep the query and fragment', () => {
    expect(signInTarget('?next=%2Fpass-giveaway%2Fdj%3Fphone%3D510%23top')).toBe(
      '/pass-giveaway/dj?phone=510#top',
    );
  });

  it.each([
    ['no next', ''],
    ['an empty next', '?next='],
    ['another host', '?next=https%3A%2F%2Fevil.example.com%2F'],
    ['a protocol-relative URL', '?next=%2F%2Fevil.example.com'],
    ['a backslash URL', '?next=%2F%5Cevil.example.com'],
    ['a tab-split protocol-relative URL', '?next=%2F%09%2Fevil.example.com'],
    ['a newline-split protocol-relative URL', '?next=%2F%0A%2Fevil.example.com'],
    ['a javascript: URL', '?next=javascript%3Aalert(1)'],
    ['a relative path', '?next=pass-giveaway'],
    ['the sign-in page itself', '?next=%2Fsign-in%3Fnext%3D%252F'],
  ])('should go home for %s', (_, search) => {
    expect(signInTarget(search)).toBe('/');
  });
});
