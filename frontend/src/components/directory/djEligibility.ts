import type { DirectoryEntry } from '../../types';

const SUBLIST_DJ_STATUS = 'Sublist DJ';
const ON_LEAVE_STATUS = 'on leave';

/** Whether Airtable gives the staff member an "On leave" status (ignoring case). */
export function hasOnLeaveStatus(entry: DirectoryEntry): boolean {
  return entry.statuses.some((s) => s.toLowerCase() === ON_LEAVE_STATUS);
}

/**
 * Why a staff member with a DJ name can't sub for a DJ shift right now, or
 * null if they can. They're on leave if their leave-of-absence dates cover
 * today or if Airtable gives them an "On leave" status (matched ignoring
 * case). Being on leave takes precedence over not being on the sublist,
 * since it's the more immediate reason.
 */
export function djIneligibility(entry: DirectoryEntry): 'on-leave' | 'not-sublist' | null {
  if (entry.on_leave || hasOnLeaveStatus(entry)) return 'on-leave';
  if (!entry.statuses.includes(SUBLIST_DJ_STATUS)) return 'not-sublist';
  return null;
}

export const DJ_INELIGIBLE_NOTES = {
  'on-leave':
    'Not eligible to sub for DJ shifts: on leave of absence from the station, so not around right now.',
  'not-sublist': 'Not eligible to sub for DJ shifts: not on the DJ sublist.',
} as const;
