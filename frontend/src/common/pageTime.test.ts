import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { pageContextParams, pageContextQuery, trackPageChanges } from './pageTime';

describe('pageContextParams', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    trackPageChanges();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('counts seconds on the current path, restarting when the path changes', () => {
    window.history.pushState({}, '', '/directory/');
    vi.advanceTimersByTime(42_500);
    expect(pageContextParams()).toMatchObject({ page: '/directory/', secs: '42' });

    // A query string change (such as a filter) is the same page
    window.history.replaceState({}, '', '/directory/?q=ann');
    vi.advanceTimersByTime(10_000);
    expect(pageContextParams()).toMatchObject({ page: '/directory/', secs: '52' });

    window.history.pushState({}, '', '/workforms/');
    vi.advanceTimersByTime(3_000);
    expect(pageContextParams()).toMatchObject({ page: '/workforms/', secs: '3' });
  });

  it('says whether the tab is showing', () => {
    expect(pageContextParams().visible).toBe('1');
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden');
    expect(pageContextParams().visible).toBe('0');
    vi.restoreAllMocks();
  });

  it('leaves slashes readable in the query string but encodes the rest', () => {
    window.history.pushState({}, '', '/directory/Ann%20Lee');
    expect(pageContextQuery()).toMatch(/^page=\/directory\/Ann%2520Lee&secs=\d+&visible=[01]$/);
  });
});
