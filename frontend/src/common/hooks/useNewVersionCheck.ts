import { useEffect, useState } from 'react';
import { builtVersion, canReloadFor, fetchDeployedVersion, reloadFor } from '../appVersion';

export const CHECK_INTERVAL_MS = 5 * 60 * 1000;
export const IDLE_BEFORE_RELOAD_MS = 10 * 60 * 1000;
export const IDLE_BEFORE_RELOAD_AFTER_TYPING_MS = 60 * 60 * 1000;
const RELOAD_CHECK_INTERVAL_MS = 1000;
const ACTIVITY_EVENTS = ['keydown', 'pointerdown', 'wheel', 'touchstart'];

/**
 * Checks every few minutes whether a newer build has been deployed. A tab that
 * finds one reloads when that's unlikely to cost anyone their work: on the next
 * page change, or once it has been idle, for longer if something was typed on
 * this page and might not be saved yet. Until then the returned version lets the
 * page offer a reload.
 *
 * @returns The deployed version this tab should reload for, or null
 */
export const useNewVersionCheck = (): string | null => {
  const [newVersion, setNewVersion] = useState<string | null>(null);

  useEffect(() => {
    const built = builtVersion();
    if (!built) return;

    let cancelled = false;
    let pending: { version: string; path: string } | null = null;
    let lastActivity = Date.now();
    let pathTypedOn: string | null = null;

    const markActive = () => {
      lastActivity = Date.now();
    };
    const markTyped = () => {
      markActive();
      pathTypedOn = window.location.pathname;
    };

    const check = async () => {
      const deployed = await fetchDeployedVersion();
      // Can't tell right now, so whatever was known last still stands
      if (cancelled || !deployed) return;
      if (deployed === built || !canReloadFor(deployed)) {
        pending = null;
      } else if (pending?.version !== deployed) {
        pending = { version: deployed, path: window.location.pathname };
      }
      setNewVersion(pending?.version ?? null);
    };

    const reloadIfSafe = () => {
      if (!pending) return;
      const path = window.location.pathname;
      const navigated = path !== pending.path;
      const idleLimit =
        pathTypedOn === path ? IDLE_BEFORE_RELOAD_AFTER_TYPING_MS : IDLE_BEFORE_RELOAD_MS;
      if (navigated || Date.now() - lastActivity >= idleLimit) {
        reloadFor(pending.version);
        pending = null;
      }
    };

    // Timers run slowly or not at all in a background tab or a sleeping laptop
    const checkWhenVisible = () => {
      if (document.visibilityState === 'visible') void check();
    };

    const checkTimer = setInterval(() => void check(), CHECK_INTERVAL_MS);
    const reloadTimer = setInterval(reloadIfSafe, RELOAD_CHECK_INTERVAL_MS);
    document.addEventListener('visibilitychange', checkWhenVisible);
    document.addEventListener('input', markTyped);
    ACTIVITY_EVENTS.forEach((event) =>
      window.addEventListener(event, markActive, { passive: true }),
    );

    return () => {
      cancelled = true;
      clearInterval(checkTimer);
      clearInterval(reloadTimer);
      document.removeEventListener('visibilitychange', checkWhenVisible);
      document.removeEventListener('input', markTyped);
      ACTIVITY_EVENTS.forEach((event) => window.removeEventListener(event, markActive));
    };
  }, []);

  return newVersion;
};
