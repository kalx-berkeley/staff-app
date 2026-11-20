/**
 * What the giveaway page just recorded, for the show page it returns to.
 *
 * The giveaway page returns to its show by going back in history when it was
 * opened from that show, so the show page's "Back" button (one page back)
 * goes where the DJ was before the show, not to the giveaway form. Going back
 * can't carry location state, so the outcome waits here instead. The show
 * page reads it when it mounts and clears it, so a reload or a later visit
 * shows the page as usual.
 *
 * @module giveawayOutcome
 */

import type { GiveawayOutcome } from './PassGiveawayForm';

let pending: { showId: string; outcome: GiveawayOutcome } | null = null;

/** Record what the giveaway page did for show *showId*. */
export const setGiveawayOutcome = (showId: string, outcome: GiveawayOutcome): void => {
  pending = { showId, outcome };
};

/** The outcome waiting for show *showId*, if any, without clearing it. */
export const peekGiveawayOutcome = (showId: string | undefined): GiveawayOutcome | null =>
  pending && pending.showId === showId ? pending.outcome : null;

/** Forget any waiting outcome. */
export const clearGiveawayOutcome = (): void => {
  pending = null;
};
