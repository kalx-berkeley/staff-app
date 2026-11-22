import { useEffect, useRef } from 'react';
import { showsAPI } from '../api';
import type { ShowResponse } from '../types';

export const DJ_REFRESH_INTERVAL_MS = 60 * 1000;

/**
 * Calls `refresh` every `intervalMs` while the tab is showing, and as soon as
 * it's brought back to the front. The DJ studio computer keeps tabs open for
 * days, so a page loaded before a show closed has to notice on its own.
 *
 * @param refresh Fetches and applies the latest data. Its errors are its own.
 * @param intervalMs How often to call it while the tab is showing
 */
export function useRefreshWhileVisible(
  refresh: () => void,
  intervalMs: number = DJ_REFRESH_INTERVAL_MS,
): void {
  const refreshRef = useRef(refresh);
  useEffect(() => {
    refreshRef.current = refresh;
  });

  useEffect(() => {
    const refreshIfVisible = () => {
      if (document.visibilityState === 'visible') refreshRef.current();
    };
    const timer = setInterval(refreshIfVisible, intervalMs);
    document.addEventListener('visibilitychange', refreshIfVisible);
    return () => {
      clearInterval(timer);
      document.removeEventListener('visibilitychange', refreshIfVisible);
    };
  }, [intervalMs]);
}

/**
 * Keeps the DJ show or giveaway page's show up to date on whether its
 * giveaway has closed (`isDjGiveawayClosed`). Only the close fields are
 * replaced, so a winner being typed in or edited isn't disturbed.
 *
 * @param showId The show's ID, from the URL
 * @param setShow The page's show state setter
 */
export function useShowCloseRecheck(
  showId: string | undefined,
  setShow: (update: (prev: ShowResponse | null) => ShowResponse | null) => void,
): void {
  useRefreshWhileVisible(() => {
    if (!showId) return;
    showsAPI
      .get(parseInt(showId))
      .then((latest) =>
        setShow((prev) =>
          prev && {
            ...prev,
            status: latest.status,
            planned_close_date: latest.planned_close_date,
            planned_close_time: latest.planned_close_time,
            planned_close_passed: latest.planned_close_passed,
          },
        ),
      )
      // The next check tries again
      .catch(() => {});
  });
}
