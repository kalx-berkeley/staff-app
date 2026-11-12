import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { pacificDateString } from '../common/dateTime';

// The filters on the promotions, staff and DJ shows pages live in the URL
// query string, so going back from a show to the list keeps them:
//   ?mine=0&assigned=hidden&q=rock&venue=3&genre=punk&status=all&sort=venue&from=2026-10-01&to=
// Anything at its default is left out of the URL. "from" defaults to 30 days
// ago, so an empty "from=" means no start date.

export type ShowSort = 'date' | 'band' | 'venue' | 'published';

export const SHOW_SORTS: readonly ShowSort[] = ['date', 'band', 'venue', 'published'];

/** The search bar's filters: free text, venue and genre. */
export interface ShowSearchFilters {
  query: string;
  venueId: number | '';
  genre: string;
}

export interface ShowListFilters<Status extends string> extends ShowSearchFilters {
  /** Only the promotions page uses this (My Shows / All Shows). */
  mineOnly: boolean;
  /** Only the DJ page uses this (Your Pre-assigned Shows → Hide). */
  hideAssigned: boolean;
  status: Status;
  sort: ShowSort;
  dateFrom: string;
  dateTo: string;
}

export interface ShowListFilterOptions<Status extends string> {
  statuses: readonly Status[];
  defaultStatus: Status;
}

const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

/** The default "From" date: 30 days ago, Pacific time. */
export const defaultDateFrom = (): string => {
  const d = new Date();
  d.setDate(d.getDate() - 30);
  return pacificDateString(d);
};

const parseDate = (value: string | null, fallback: string): string => {
  if (value === null) return fallback;
  return value === '' || DATE_PATTERN.test(value) ? value : fallback;
};

export function parseShowListFilters<Status extends string>(
  params: URLSearchParams,
  options: ShowListFilterOptions<Status>,
): ShowListFilters<Status> {
  const venue = params.get('venue') ?? '';
  const status = params.get('status') as Status | null;
  const sort = params.get('sort') as ShowSort | null;
  return {
    mineOnly: params.get('mine') !== '0',
    hideAssigned: params.get('assigned') === 'hidden',
    query: params.get('q') ?? '',
    venueId: /^\d+$/.test(venue) ? parseInt(venue, 10) : '',
    genre: params.get('genre') ?? '',
    status: status && options.statuses.includes(status) ? status : options.defaultStatus,
    sort: sort && SHOW_SORTS.includes(sort) ? sort : 'date',
    dateFrom: parseDate(params.get('from'), defaultDateFrom()),
    dateTo: parseDate(params.get('to'), ''),
  };
}

/** Query string parameters for the filters, leaving out anything at its default. */
export function showListFilterParams<Status extends string>(
  filters: ShowListFilters<Status>,
  options: ShowListFilterOptions<Status>,
): URLSearchParams {
  const params = new URLSearchParams();
  if (!filters.mineOnly) params.set('mine', '0');
  if (filters.hideAssigned) params.set('assigned', 'hidden');
  if (filters.query) params.set('q', filters.query);
  if (filters.venueId !== '') params.set('venue', String(filters.venueId));
  if (filters.genre) params.set('genre', filters.genre);
  if (filters.status !== options.defaultStatus) params.set('status', filters.status);
  if (filters.sort !== 'date') params.set('sort', filters.sort);
  if (filters.dateFrom !== defaultDateFrom()) params.set('from', filters.dateFrom);
  if (filters.dateTo) params.set('to', filters.dateTo);
  return params;
}

/**
 * The shows page filters, read from and written to the URL. `options` must be
 * a module-level constant. Pass every change made at once in one call: two
 * calls in the same event would each start from the same URL, and the second
 * would undo the first.
 */
export function useShowListFilters<Status extends string>(
  options: ShowListFilterOptions<Status>,
): [ShowListFilters<Status>, (changes: Partial<ShowListFilters<Status>>) => void] {
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = useMemo(
    () => parseShowListFilters(searchParams, options),
    [searchParams, options],
  );
  const updateFilters = useCallback(
    (changes: Partial<ShowListFilters<Status>>) => {
      // Replace rather than push, so typing a search doesn't fill the history.
      setSearchParams(showListFilterParams({ ...filters, ...changes }, options), {
        replace: true,
      });
    },
    [filters, options, setSearchParams],
  );
  return [filters, updateFilters];
}
