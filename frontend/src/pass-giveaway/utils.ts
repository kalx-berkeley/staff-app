import type { UserResponse } from '../common/types';
import type { PassResponse } from './types';

// Staging-only: lets a staff member with active Sublist DJ status access the
// DJ view, ahead of this being rolled out to production.
export function isStagingSublistDjStaff(user: Pick<UserResponse, 'role' | 'is_staging' | 'profile'> | null | undefined): boolean {
  return !!user?.is_staging && user.role === 'staff' && !!user.profile?.is_sublist_dj;
}

// The backend allows each DJ one on-air pass pair giveaway per show within
// this window (one DJ shift); see PassService.giveaway_pass.
export const DJ_SHOW_GIVEAWAY_WINDOW_HOURS = 4;

// The pass pair this DJ already gave away for the show within the window, if
// any. Names are compared ignoring case and surrounding spaces.
export function findRecentDjGiveaway(
  passes: Pick<PassResponse, 'given_away_by_dj' | 'given_away_at'>[],
  djName: string,
  now: Date = new Date(),
): Pick<PassResponse, 'given_away_by_dj' | 'given_away_at'> | undefined {
  const name = djName.trim().toLowerCase();
  if (!name) return undefined;
  const windowStart = now.getTime() - DJ_SHOW_GIVEAWAY_WINDOW_HOURS * 60 * 60 * 1000;
  return passes.find(
    (p) =>
      p.given_away_by_dj?.trim().toLowerCase() === name &&
      !!p.given_away_at &&
      new Date(p.given_away_at).getTime() >= windowStart,
  );
}
