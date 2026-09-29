import { describe, it, expect } from 'vitest';
import { DEFAULT_SORT, parseViewState, viewStateParams } from './directoryUrlState';

describe('directory URL state', () => {
  it('parses search, filters, and sort from the query string', () => {
    const state = parseViewState(
      new URLSearchParams('q=music&dept=News&dept=Music&status=Paid+Staff&sort=-email'),
    );
    expect(state).toEqual({
      query: 'music',
      departments: ['News', 'Music'],
      statuses: ['Paid Staff'],
      sort: { id: 'email', desc: true },
    });
  });

  it('defaults to no filters, sorted by name', () => {
    expect(parseViewState(new URLSearchParams(''))).toEqual({
      query: '',
      departments: [],
      statuses: [],
      sort: DEFAULT_SORT,
    });
  });

  it('ignores an unknown sort column', () => {
    expect(parseViewState(new URLSearchParams('sort=phone')).sort).toEqual(DEFAULT_SORT);
  });

  it('round-trips, leaving defaults out of the query string', () => {
    const params = 'q=music&dept=News&status=Active&sort=dj_name';
    expect(viewStateParams(parseViewState(new URLSearchParams(params))).toString()).toBe(params);
    expect(viewStateParams(parseViewState(new URLSearchParams('sort=name'))).toString()).toBe('');
  });
});
