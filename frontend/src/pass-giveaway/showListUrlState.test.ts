import { describe, it, expect } from 'vitest';
import {
  defaultDateFrom,
  parseShowListFilters,
  showListFilterParams,
  type ShowListFilterOptions,
} from './showListUrlState';

type Status = 'all' | 'draft' | 'published' | 'closed';
const OPTIONS: ShowListFilterOptions<Status> = {
  statuses: ['all', 'draft', 'published', 'closed'],
  defaultStatus: 'published',
};

const parse = (query: string) => parseShowListFilters(new URLSearchParams(query), OPTIONS);

describe('show list URL state', () => {
  it('uses the defaults when the URL has no filters', () => {
    expect(parse('')).toEqual({
      mineOnly: true,
      hideAssigned: false,
      query: '',
      venueId: '',
      genre: '',
      status: 'published',
      sort: 'date',
      dateFrom: defaultDateFrom(),
      dateTo: '',
    });
  });

  it('leaves defaults out of the URL', () => {
    expect(showListFilterParams(parse(''), OPTIONS).toString()).toBe('');
  });

  it('round-trips every filter', () => {
    const query = 'mine=0&assigned=hidden&q=rock+night&venue=3&genre=punk%2C+jazz&status=all&sort=venue&from=2026-10-01&to=2026-12-31';
    const filters = parse(query);
    expect(filters).toEqual({
      mineOnly: false,
      hideAssigned: true,
      query: 'rock night',
      venueId: 3,
      genre: 'punk, jazz',
      status: 'all',
      sort: 'venue',
      dateFrom: '2026-10-01',
      dateTo: '2026-12-31',
    });
    expect(showListFilterParams(filters, OPTIONS).toString()).toBe(query);
  });

  it('keeps a cleared From date apart from the default one', () => {
    const filters = parse('from=');
    expect(filters.dateFrom).toBe('');
    expect(showListFilterParams(filters, OPTIONS).toString()).toBe('from=');
  });

  it('ignores values it does not recognize', () => {
    expect(parse('status=bogus&sort=bogus&venue=abc&from=nope&to=nope')).toMatchObject({
      status: 'published',
      sort: 'date',
      venueId: '',
      dateFrom: defaultDateFrom(),
      dateTo: '',
    });
  });
});
