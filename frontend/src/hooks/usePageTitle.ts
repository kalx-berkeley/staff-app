import { useEffect } from 'react';

const BASE_TITLE = 'Radio Pass Giveaway';

/**
 * Sets the browser tab/history title for the current page. Falsy titles (e.g.
 * while a page's own data is still loading) fall back to the base app title
 * rather than rendering "undefined" or an empty string in browser history.
 */
export function usePageTitle(title: string | null | undefined): void {
  useEffect(() => {
    document.title = title ? `${title} · ${BASE_TITLE}` : BASE_TITLE;
  }, [title]);
}
