/**
 * Spotting that a deploy happened while a tab was open, and reloading the tab
 * so it isn't left running old code against the new backend.
 *
 * @module appVersion
 */

const RELOADED_FOR_VERSION_KEY = 'kalx_reloaded_for_version';
const CHUNK_RELOAD_AT_KEY = 'kalx_chunk_reload_at';
// A chunk still failing this soon after a reload isn't fixed by reloading again
const CHUNK_RELOAD_COOLDOWN_MS = 60 * 1000;

/** This build's version, set by the deploy. Undefined in local dev. */
export const builtVersion = (): string | undefined =>
  import.meta.env.VITE_RELEASE_VERSION || import.meta.env.VITE_COMMIT_SHA || undefined;

/**
 * The deployed version, or null when it can't be told, which is normal while
 * the backend restarts. This uses fetch, not the shared API client, because that
 * client answers a 401 by leaving the page, and a background check mustn't send
 * someone whose session expired off the page they're on.
 */
export const fetchDeployedVersion = async (): Promise<string | null> => {
  try {
    const response = await fetch('/api/version', { cache: 'no-store' });
    if (!response.ok) return null;
    const { version } = await response.json();
    return typeof version === 'string' && version ? version : null;
  } catch {
    return null;
  }
};

/**
 * Whether reloading could still help a tab that doesn't match `version`. A tab
 * reloads at most once per deployed version, so a mismatch that a reload doesn't
 * fix can't become a reload loop. No sessionStorage means no way to tell, so no.
 */
export const canReloadFor = (version: string): boolean => {
  try {
    return sessionStorage.getItem(RELOADED_FOR_VERSION_KEY) !== version;
  } catch {
    return false;
  }
};

/** Reload to pick up `version`, remembering that this tab tried. */
export const reloadFor = (version: string): void => {
  try {
    sessionStorage.setItem(RELOADED_FOR_VERSION_KEY, version);
  } catch {
    return;
  }
  window.location.reload();
};

/**
 * Answers Vite's vite:preloadError: a tab from before a deploy asked for a page's
 * code, and the deploy removed it. If the reload doesn't help, or doesn't happen,
 * the failure reaches the ErrorBoundary.
 */
export const reloadAfterChunkLoadError = (): void => {
  try {
    const lastReload = Number(sessionStorage.getItem(CHUNK_RELOAD_AT_KEY));
    if (Date.now() - lastReload < CHUNK_RELOAD_COOLDOWN_MS) return;
    sessionStorage.setItem(CHUNK_RELOAD_AT_KEY, String(Date.now()));
  } catch {
    return;
  }
  window.location.reload();
};
