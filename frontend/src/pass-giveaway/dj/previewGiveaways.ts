/**
 * Pretend giveaways for the DJ view's preview mode (see
 * `canRecordDjGiveaways`). A previewer's Give Away isn't sent to the backend,
 * so it's kept here instead, for this browser tab only, and the DJ show list
 * and show page treat it like a real giveaway: the same "View" button, the
 * same warnings and the same hidden "I'm off the mic" button.
 */
import { DJ_SHOW_GIVEAWAY_WINDOW_HOURS } from '../utils';

export interface PreviewGiveaway {
  show_id: number;
  given_away_by_dj: string;
  given_away_at: string;
  recipient_name: string;
}

const STORAGE_KEY = 'kalx_dj_preview_giveaways';
const WINDOW_MS = DJ_SHOW_GIVEAWAY_WINDOW_HOURS * 60 * 60 * 1000;

/** The pretend giveaways from the last DJ_SHOW_GIVEAWAY_WINDOW_HOURS. */
export function getPreviewGiveaways(now: Date = new Date()): PreviewGiveaway[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    const all = raw ? (JSON.parse(raw) as PreviewGiveaway[]) : [];
    if (!Array.isArray(all)) return [];
    return all.filter((g) => now.getTime() - new Date(g.given_away_at).getTime() < WINDOW_MS);
  } catch {
    return [];
  }
}

/** Remembers a pretend giveaway. Storage failures are ignored. */
export function recordPreviewGiveaway(giveaway: Omit<PreviewGiveaway, 'given_away_at'>, now: Date = new Date()): void {
  try {
    const entries = [...getPreviewGiveaways(now), { ...giveaway, given_away_at: now.toISOString() }];
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  } catch {
    // Private browsing or blocked storage: the preview just forgets it.
  }
}
