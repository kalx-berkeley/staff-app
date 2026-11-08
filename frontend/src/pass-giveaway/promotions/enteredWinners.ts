import type { EnteredOnAirWinner, EnteredStaffWinner, PassResponse } from '../types';

// Winners a promotions rep types in on the show form, for a show that replaces
// a cancelled, postponed or moved one. See
// docs/pass-giveaway/specs/preassigned-winners/plan.md.

export interface OnAirWinnerRow {
  key: number;
  recipient_name: string;
  recipient_phone: string;
  recipient_email: string;
  given_away_by_dj: string;
}

export interface StaffWinnerRow {
  key: number;
  staff_input: string;
  staff_id: number | '';
  has_guest: boolean;
  guest_name: string;
}

export interface FreePasses {
  pairs: number;
  staff: number;
}

let nextKey = 1;
export const emptyOnAirRow = (): OnAirWinnerRow => ({
  key: nextKey++,
  recipient_name: '',
  recipient_phone: '',
  recipient_email: '',
  given_away_by_dj: '',
});
export const emptyStaffRow = (): StaffWinnerRow => ({
  key: nextKey++,
  staff_input: '',
  staff_id: '',
  has_guest: false,
  guest_name: '',
});

/**
 * The passes entered winners can go on once a show's pass counts change. Mirrors
 * the backend: raising a count adds free passes, cutting it removes free ones
 * first, and pass pairs reserved for a DJ never count.
 */
export const freePassesAfterAdjustment = (
  passes: PassResponse[],
  numPassPairs: number,
  totalStaffPasses: number,
): FreePasses => {
  const pairs = passes.filter((p) => p.pass_type === 'pair');
  const staff = passes.filter((p) => p.pass_type === 'staff');
  const freePairs = pairs.filter((p) => p.status === 'available' && !p.preassigned_dj).length;
  const freeStaff = staff.filter((p) => p.status === 'available').length;
  return {
    pairs: Math.max(0, freePairs + numPassPairs - pairs.length),
    staff: Math.max(0, freeStaff + totalStaffPasses - staff.length),
  };
};

export const staffPassesNeeded = (rows: StaffWinnerRow[]) =>
  rows.reduce((n, r) => n + (r.has_guest ? 2 : 1), 0);

/** The first problem with the entered winners, or null when they can be saved. */
export const enteredWinnersError = (
  onAirRows: OnAirWinnerRow[],
  staffRows: StaffWinnerRow[],
  free: FreePasses,
  requiresEmail: boolean,
  guestRequiresName: boolean,
): string | null => {
  for (const [i, row] of onAirRows.entries()) {
    if (!row.recipient_name.trim()) return `On-air winner ${i + 1} needs a name`;
    if (!row.recipient_phone.replace(/\D/g, '')) return `On-air winner ${i + 1} needs a phone number`;
    if (requiresEmail && !row.recipient_email.trim()) {
      return `On-air winner ${i + 1} needs an email address, which this show's guest list requires`;
    }
  }
  const seen = new Set<number>();
  for (const [i, row] of staffRows.entries()) {
    if (row.staff_id === '') return `Staff winner ${i + 1}: pick a staff member from the list`;
    if (seen.has(row.staff_id)) return `Staff winner ${i + 1} is entered more than once`;
    seen.add(row.staff_id);
    if (row.has_guest && guestRequiresName && !row.guest_name.trim()) {
      return `Staff winner ${i + 1}'s +1 guest needs a name, which this show's guest list requires`;
    }
  }
  if (onAirRows.length > free.pairs) {
    return `There are more on-air winners than free pass pairs (${free.pairs})`;
  }
  if (staffPassesNeeded(staffRows) > free.staff) {
    return `The staff winners and their guests need more staff passes than are free (${free.staff})`;
  }
  return null;
};

export const toOnAirPayload = (rows: OnAirWinnerRow[]): EnteredOnAirWinner[] =>
  rows.map((r) => ({
    recipient_name: r.recipient_name.trim(),
    recipient_phone: r.recipient_phone.trim(),
    recipient_email: r.recipient_email.trim() || null,
    given_away_by_dj: r.given_away_by_dj.trim() || null,
  }));

export const toStaffPayload = (rows: StaffWinnerRow[]): EnteredStaffWinner[] =>
  rows.map((r) => ({
    staff_id: r.staff_id as number,
    has_guest: r.has_guest,
    guest_name: r.has_guest ? r.guest_name.trim() || null : null,
  }));
