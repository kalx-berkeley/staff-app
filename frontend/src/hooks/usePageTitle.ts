import { useEffect } from 'react';

const BASE_TITLE = 'Radio Pass Giveaway';

/**
 * Sets the browser tab/history title for the current page. Falsy titles (e.g.
 * while a page's own data is still loading) fall back to the base title
 * rather than rendering "undefined" or an empty string in browser history.
 * The base title defaults to the Radio Pass Giveaway sub-site's name.
 */
export function usePageTitle(title: string | null | undefined, baseTitle = BASE_TITLE): void {
  useEffect(() => {
    document.title = title ? `${title} · ${baseTitle}` : baseTitle;
  }, [title, baseTitle]);
}
