import { describe, it, expect } from 'vitest';
import { filterVenues } from './venueSearch';
import type { VenueResponse } from './types';

const venue = (
  id: number,
  name: string,
  address: string,
  reps: { name: string | null; email: string }[],
) => ({ id, name, address, owner_details: reps }) as VenueResponse;

const venues = [
  venue(1, 'The Fox Theater', '1807 Telegraph Ave', [
    { name: 'Ana Lopez', email: 'ana@kalx.berkeley.edu' },
    { name: 'Ben Ito', email: 'ben@kalx.berkeley.edu' },
  ]),
  venue(2, 'Cornerstone', '2367 Shattuck Ave', [{ name: 'Cara Diaz', email: 'cara@kalx.berkeley.edu' }]),
  venue(3, 'Rickshaw Stop', '155 Fell St', []),
];

const ids = (list: VenueResponse[]) => list.map((v) => v.id);

describe('filterVenues', () => {
  it('returns every venue for a blank query', () => {
    expect(ids(filterVenues(venues, '   '))).toEqual([1, 2, 3]);
  });

  it('matches venue names, ignoring case', () => {
    expect(ids(filterVenues(venues, 'fox'))).toEqual([1]);
  });

  it('matches any rep of a venue with several reps, by name or email', () => {
    expect(ids(filterVenues(venues, 'ito'))).toEqual([1]);
    expect(ids(filterVenues(venues, 'cara@'))).toEqual([2]);
  });

  it('needs every word to match, across venue and rep', () => {
    expect(ids(filterVenues(venues, 'fox ana'))).toEqual([1]);
    expect(ids(filterVenues(venues, 'fox cara'))).toEqual([]);
  });

  it('only matches addresses when asked to', () => {
    expect(ids(filterVenues(venues, 'shattuck'))).toEqual([]);
    expect(ids(filterVenues(venues, 'shattuck', { includeAddress: true }))).toEqual([2]);
  });
});
