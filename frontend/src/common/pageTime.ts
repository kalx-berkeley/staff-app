/**
 * Which page this tab is on and how long it has been there, sent as query
 * arguments on background polls (/api/version, /api/dj/spin-matches) so the
 * access logs show where people sit. The backend ignores them.
 *
 * @module pageTime
 */

let currentPath = window.location.pathname;
let pageStartedAt = Date.now();
let tracking = false;

/** Restart the clock if the path changed. Query string and hash changes don't count. */
const notePathChange = (): void => {
  const path = window.location.pathname;
  if (path !== currentPath) {
    currentPath = path;
    pageStartedAt = Date.now();
  }
};

/**
 * Start noticing page changes. The sub-sites' routers move between pages with
 * history.pushState/replaceState, which fire no event, so those are wrapped.
 * Call once at startup; later calls do nothing.
 */
export const trackPageChanges = (): void => {
  if (tracking) return;
  tracking = true;
  for (const method of ['pushState', 'replaceState'] as const) {
    const original = window.history[method];
    window.history[method] = function (
      this: History,
      ...args: Parameters<History['pushState']>
    ) {
      original.apply(this, args);
      notePathChange();
    };
  }
  window.addEventListener('popstate', notePathChange);
};

/**
 * The query arguments describing this tab's page.
 *
 * @returns page (the path, without its query string), secs (whole seconds on
 *   that path) and visible ("1" when the tab is showing, "0" in the background)
 */
export const pageContextParams = (): { page: string; secs: string; visible: string } => {
  notePathChange();
  return {
    page: currentPath,
    secs: String(Math.floor((Date.now() - pageStartedAt) / 1000)),
    visible: document.visibilityState === 'visible' ? '1' : '0',
  };
};

/**
 * pageContextParams as a query string, leaving slashes unencoded (they're
 * allowed in a query string) so the logged path reads like one.
 *
 * @returns For example "page=/pass-giveaway/dj&secs=1834&visible=1"
 */
export const pageContextQuery = (): string =>
  new URLSearchParams(pageContextParams()).toString().replace(/%2F/gi, '/');
