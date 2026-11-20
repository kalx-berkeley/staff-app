import { useCallback, useMemo } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';

// The filters on the venue and promoter list pages live in the URL query
// string, like the shows pages' (showListUrlState.ts), so going back to the
// list keeps them. Anything at its default is left out of the URL.

/**
 * String-valued page filters, read from and written to the URL. `defaults`
 * must be a module-level constant; its keys are the query parameter names.
 * Pass every change made at once in one call.
 */
export function useUrlParams<K extends string>(
  defaults: Readonly<Record<K, string>>,
): [Record<K, string>, (changes: Partial<Record<K, string>>) => void] {
  const [searchParams, setSearchParams] = useSearchParams();
  const values = useMemo(() => {
    const result: Record<K, string> = { ...defaults };
    for (const key of Object.keys(defaults) as K[]) {
      const value = searchParams.get(key);
      if (value !== null) result[key] = value;
    }
    return result;
  }, [searchParams, defaults]);
  const update = useCallback(
    (changes: Partial<Record<K, string>>) => {
      const next = { ...values, ...changes };
      const params = new URLSearchParams();
      for (const key of Object.keys(defaults) as K[]) {
        if (next[key] !== defaults[key]) params.set(key, next[key]);
      }
      // Replace rather than push, so typing a search doesn't fill the history.
      setSearchParams(params, { replace: true });
    },
    [values, defaults, setSearchParams],
  );
  return [values, update];
}

/** Location state a list page passes to the page it opens, so that page can return to it. */
export interface ListReturnState {
  listSearch?: string;
}

/** The location state that remembers this list page's current filters. */
export function useListReturnState(): ListReturnState {
  const { search } = useLocation();
  return { listSearch: search };
}

/** The list page's URL with the filters it was opened from, if any. */
export function useReturnToList(listPath: string): string {
  const { state } = useLocation();
  const listSearch = (state as ListReturnState | null)?.listSearch ?? '';
  return listPath + listSearch;
}
