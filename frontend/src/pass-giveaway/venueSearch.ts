import type { VenueResponse } from './types';

/**
 * Filter venues by a search query.
 *
 * The query is split into words, and a venue matches when every word appears
 * in its name, address (when `includeAddress` is set), or any of its KALX
 * promotions reps' names or emails. Matching ignores case.
 */
export function filterVenues(
  venues: VenueResponse[],
  query: string,
  { includeAddress = false }: { includeAddress?: boolean } = {},
): VenueResponse[] {
  const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (terms.length === 0) return venues;
  return venues.filter((venue) => {
    const searchable = [
      venue.name,
      includeAddress ? venue.address : '',
      ...(venue.owner_details ?? []).flatMap((rep) => [rep.name ?? '', rep.email]),
    ]
      .join('\n')
      .toLowerCase();
    return terms.every((term) => searchable.includes(term));
  });
}
