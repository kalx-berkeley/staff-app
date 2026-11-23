/**
 * What the giveaway page just did, for the show page it returns to.
 *
 * The giveaway page returns to its show by going back in history when it was
 * opened from that show, so the show page's "Back" button (one page back)
 * goes where the DJ was before the show, not to the giveaway form. Going back
 * can't carry location state, so the outcome waits here instead. The show
 * page reads it when it mounts and clears it, so a reload or a later visit
 * shows the page as usual. `DJLayout` also clears it when the DJ goes
 * anywhere other than the show and its giveaway page.
 *
 * Opening the giveaway form records `'opened'` with the page's visit ID.
 * Give Away and Tried replace that with their outcome. If the DJ leaves with
 * neither (browser Back or "Back to Show"), the show page still finds
 * `'opened'` and asks whether they announced the passes and got no callers.
 *
 * @module giveawayOutcome
 */

import type { GiveawayOutcome } from './PassGiveawayForm';

/** A recorded outcome, or `'opened'` when the DJ left without recording one. */
export type GiveawayHandoff = GiveawayOutcome | 'opened';

let pending: { showId: string; outcome: GiveawayHandoff; visitId: string | null } | null = null;

/** Record what the giveaway page did for show *showId*. */
export const setGiveawayOutcome = (showId: string, outcome: GiveawayOutcome): void => {
  pending = { showId, outcome, visitId: pending?.showId === showId ? pending.visitId : null };
};

/**
 * Record that the DJ opened show *showId*'s giveaway form, in giveaway page
 * visit *visitId*, and hasn't recorded anything yet.
 */
export const markGiveawayOpened = (showId: string, visitId: string | null): void => {
  pending = { showId, outcome: 'opened', visitId };
};

/** The outcome waiting for show *showId*, if any, without clearing it. */
export const peekGiveawayOutcome = (showId: string | undefined): GiveawayHandoff | null =>
  pending && pending.showId === showId ? pending.outcome : null;

/** The giveaway page visit waiting for show *showId*, if any. */
export const peekGiveawayVisitId = (showId: string | undefined): string | null =>
  pending && pending.showId === showId ? pending.visitId : null;

/** Forget any waiting outcome. */
export const clearGiveawayOutcome = (): void => {
  pending = null;
};
