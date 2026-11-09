/**
 * KALX Staff Analytics tracking for the pass giveaway: DJ studio and station
 * office guest sessions, and visits to a show's "I'm off the mic" page.
 *
 * Every call is fire-and-forget: tracking never shows an error or breaks the
 * page. The backend decides what to record (it ignores promotions staff
 * previewing the DJ view, for example).
 */
import { useEffect, useRef } from 'react';
import apiClient from '../common/api';
import type { UserResponse } from '../common/types';

const SESSION_KEY = 'kalx_guest_session';
const VISIT_KEY = 'kalx_giveaway_visit';

/** A new session starts after this long without using the page. */
export const SESSION_IDLE_MS = 30 * 60 * 1000;
/** A reload within this long continues the same giveaway page visit. */
export const VISIT_RELOAD_MS = 10 * 60 * 1000;

const newId = (): string => {
  try {
    return crypto.randomUUID();
  } catch {
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
  }
};

const send = (method: 'post' | 'put', url: string, body: unknown) => {
  try {
    Promise.resolve(apiClient[method](url, body)).catch(() => {});
  } catch {
    // Tracking never breaks the page
  }
};

const read = <T,>(key: string): T | null => {
  try {
    const raw = sessionStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
};

const write = (key: string, value: unknown) => {
  try {
    sessionStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage unavailable
  }
};

/** Whether *user* is a DJ studio or station office guest (not signed in). */
export const isNetworkGuest = (user: UserResponse | null): boolean =>
  !!user && !user.email && (user.is_dj_network || user.is_station_office_network);

/**
 * Count this tab's guest session: one per tab, and a new one after 30
 * minutes without a click or key press.
 */
export function useGuestSession(enabled: boolean): void {
  useEffect(() => {
    if (!enabled) return;
    const touch = () => {
      const now = Date.now();
      const session = read<{ id: string; at: number }>(SESSION_KEY);
      if (!session || now - session.at > SESSION_IDLE_MS) {
        const id = newId();
        write(SESSION_KEY, { id, at: now });
        send('post', '/pass-giveaway/analytics/session', { session_id: id });
      } else if (now - session.at > 60 * 1000) {
        write(SESSION_KEY, { ...session, at: now });
      }
    };
    touch();
    window.addEventListener('pointerdown', touch);
    window.addEventListener('keydown', touch);
    return () => {
      window.removeEventListener('pointerdown', touch);
      window.removeEventListener('keydown', touch);
    };
  }, [enabled]);
}

/** This tab's visit ID for the show's giveaway page, continuing it after a quick reload. */
export function giveawayVisitId(showId: number): string {
  const now = Date.now();
  const visit = read<{ id: string; showId: number; at: number }>(VISIT_KEY);
  const id = visit && visit.showId === showId && now - visit.at < VISIT_RELOAD_MS ? visit.id : newId();
  write(VISIT_KEY, { id, showId, at: now });
  return id;
}

/**
 * Record a visit to the show's "I'm off the mic" page, and which DJ it
 * belongs to (the name field at the top of the page, sent again a moment
 * after it changes). Returns the visit ID, to send with a giveaway or
 * "tried" click.
 */
export function useGiveawayVisit(
  showId: number | null,
  djName: string,
  enabled: boolean,
): string | null {
  const visitRef = useRef<{ showId: number; id: string } | null>(null);
  const sentName = useRef<string | null>(null);

  if (enabled && showId !== null && visitRef.current?.showId !== showId) {
    visitRef.current = { showId, id: giveawayVisitId(showId) };
    sentName.current = null;
  }
  const visitId = enabled ? (visitRef.current?.id ?? null) : null;

  useEffect(() => {
    if (!visitId || showId === null) return;
    sentName.current = djName.trim();
    send('post', '/pass-giveaway/analytics/giveaway-visits', {
      visit_id: visitId,
      show_id: showId,
      dj_name: djName.trim() || null,
    });
    // Only when the visit starts; name changes are sent below
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visitId, showId]);

  useEffect(() => {
    if (!visitId || sentName.current === null || sentName.current === djName.trim()) return;
    const timer = setTimeout(() => {
      sentName.current = djName.trim();
      send('put', `/pass-giveaway/analytics/giveaway-visits/${visitId}/dj`, {
        dj_name: djName.trim() || null,
      });
    }, 1500);
    return () => clearTimeout(timer);
  }, [visitId, djName]);

  return visitId;
}
