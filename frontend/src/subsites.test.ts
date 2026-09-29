import { describe, it, expect, afterEach } from 'vitest';
import { currentSubsiteRoot, subsiteForPath } from './subsites';

describe('subsiteForPath', () => {
  it('matches a sub-site by its base path and anything under it', () => {
    expect(subsiteForPath('/pass-giveaway')?.basePath).toBe('/pass-giveaway');
    expect(subsiteForPath('/pass-giveaway/')?.basePath).toBe('/pass-giveaway');
    expect(subsiteForPath('/pass-giveaway/staff/shows/12')?.basePath).toBe('/pass-giveaway');
  });

  it('returns null for the home page and unrelated paths', () => {
    expect(subsiteForPath('/')).toBeNull();
    expect(subsiteForPath('/pass-giveaway-old/x')).toBeNull();
    expect(subsiteForPath('/unknown')).toBeNull();
  });
});

describe('currentSubsiteRoot', () => {
  afterEach(() => {
    window.history.pushState({}, '', '/');
  });

  it("returns the current sub-site's root", () => {
    window.history.pushState({}, '', '/pass-giveaway/promotions/shows');
    expect(currentSubsiteRoot()).toBe('/pass-giveaway/');
  });

  it('returns / outside every sub-site', () => {
    window.history.pushState({}, '', '/');
    expect(currentSubsiteRoot()).toBe('/');
  });
});
