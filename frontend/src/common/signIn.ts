// Signing in from the station office network. Apache lets that network use the
// /pass-giveaway/ pages without a Google login, so loading one never asks for
// it. /sign-in isn't one of those pages, so Apache sends anyone without a
// session through Google first, and main.tsx then sends them on to `next`.

export const SIGN_IN_PATH = '/sign-in';

/** URL that signs the user in with Google, then returns to `path`. */
export function signInUrl(path: string): string {
  return `${SIGN_IN_PATH}?next=${encodeURIComponent(path)}`;
}

/** Whether `pathname` is the sign-in handoff page. */
export function isSignInPath(pathname: string): boolean {
  return pathname === SIGN_IN_PATH || pathname === `${SIGN_IN_PATH}/`;
}

/**
 * Where /sign-in sends the user once signed in: `next` when it's a path on
 * this site, or else the home page. Anything else (another host, or /sign-in
 * itself) would make the page an open redirect or a loop.
 *
 * `next` is resolved the way the browser will resolve it rather than checked
 * as a string, since browsers also read forms like `/\host` and `/<tab>/host`
 * as another host.
 */
export function signInTarget(search: string, origin: string = window.location.origin): string {
  const next = new URLSearchParams(search).get('next');
  if (!next?.startsWith('/')) return '/';
  let url: URL;
  try {
    url = new URL(next, origin);
  } catch {
    return '/';
  }
  if (url.origin !== origin || isSignInPath(url.pathname)) return '/';
  return url.pathname + url.search + url.hash;
}
