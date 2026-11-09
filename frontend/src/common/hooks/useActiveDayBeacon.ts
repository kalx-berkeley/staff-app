import { useEffect } from 'react';
import apiClient from '../api';
import type { UserResponse } from '../types';

const STORAGE_PREFIX = 'kalx_active_day:';

/** Today's date in Pacific time, as YYYY-MM-DD. */
export const pacificToday = (): string =>
  new Date().toLocaleDateString('en-CA', { timeZone: 'America/Los_Angeles' });

/**
 * Tell KALX Staff Analytics that the signed-in user used *subsite* today. Sent
 * at most once per sub-site per day from this browser (the backend also
 * deduplicates), never for guests or while impersonating, and never in a way
 * that can break the page.
 */
export function useActiveDayBeacon(user: UserResponse | null, subsite: string): void {
  const eligible =
    !!user?.email &&
    !user.impersonating_email &&
    (user.role === 'promotions' || user.role === 'staff');

  useEffect(() => {
    if (!eligible) return;
    const key = `${STORAGE_PREFIX}${subsite}`;
    const today = pacificToday();
    try {
      if (localStorage.getItem(key) === today) return;
      localStorage.setItem(key, today);
    } catch {
      // Storage unavailable: the backend still deduplicates
    }
    try {
      Promise.resolve(apiClient.post('/analytics/beacon', { subsite })).catch(() => {});
    } catch {
      // Tracking never breaks the page
    }
  }, [eligible, subsite]);
}
