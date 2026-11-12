import type { UserResponse } from '../common/types';
import { formatDateValue } from '../common/utils';
import type {
  AgeRestriction,
  GuestFallback,
  MovieRating,
  PassResponse,
  ShowResponse,
  VenueType,
  WheelchairAccessible,
} from './types';

// Staging-only: lets a staff member with active Sublist DJ status access the
// DJ view, ahead of this being rolled out to production.
export function isStagingSublistDjStaff(user: Pick<UserResponse, 'role' | 'is_staging' | 'profile'> | null | undefined): boolean {
  return !!user?.is_staging && user.role === 'staff' && !!user.profile?.is_sublist_dj;
}

// Whether the backend lets this user really record a pass giveaway or a Tried
// attempt (`check_dj_giveaway_access`): a request from the DJ studio network,
// or, in staging, Sublist DJ staff. Everyone else on the DJ view (promotions
// staff at home, or someone impersonating the DJ studio network) gets a
// preview that runs the same flow without recording anything.
export function canRecordDjGiveaways(
  user: Pick<UserResponse, 'role' | 'is_staging' | 'profile' | 'is_dj_network' | 'is_impersonating_dj_network'> | null | undefined,
): boolean {
  if (!user) return false;
  return (user.is_dj_network && !user.is_impersonating_dj_network) || isStagingSublistDjStaff(user);
}

// Whether the signed-in user can use the Promotions → Admin page: site admins
// and promotions admins. Like the backend's check, this describes the real
// user, not anyone they're impersonating.
export function canUsePassGiveawayAdmin(user: Pick<UserResponse, 'is_site_admin' | 'is_promotions_admin'> | null | undefined): boolean {
  return !!user?.is_site_admin || !!user?.is_promotions_admin;
}

// Whether the signed-in user is impersonating someone, or a network (staging).
export function isImpersonating(user: Pick<UserResponse, 'impersonating_email' | 'is_impersonating_dj_network' | 'is_impersonating_station_office_network'> | null | undefined): boolean {
  return (
    !!user?.impersonating_email ||
    !!user?.is_impersonating_dj_network ||
    !!user?.is_impersonating_station_office_network
  );
}

// Whether to link to the Promotions → Admin page. Hidden while impersonating,
// so the navigation matches what the impersonated person sees, though the page
// itself still works.
export function showsPassGiveawayAdminLink(user: UserResponse | null | undefined): boolean {
  return canUsePassGiveawayAdmin(user) && !isImpersonating(user);
}

// My Passes pages hide passes for shows more than this many days in the past.
/** Shown where "🆕" staff (not yet Active) would claim a staff pass. */
/** How a list or card describes a guest fallback that puts the guest on the alternate list. */
export const waitingFallbackNote = (fallback: GuestFallback): string => {
  if (fallback === 'wait') return ' (guest will wait on the alternate list)';
  if (fallback === 'wait_then_release') {
    return " (guest will wait on the alternate list; staff's pass is released if they don't have one at close)";
  }
  return '';
};

/** The same note for a guest who has a pass, and only waits if they lose it. */
export const seatedFallbackNote = (fallback: GuestFallback): string => {
  if (fallback === 'wait') return ' (goes on the alternate list if bumped)';
  if (fallback === 'wait_then_release') {
    return " (goes on the alternate list if bumped; staff's pass is released if they don't have one at close)";
  }
  return '';
};

/** The table Publicity staff at co-announce shows, using tabler passes. */
export const KALX_TABLE_NAME = 'KALX Co-Announce Table';

/** How many tabler passes a show gets when Co-Announce is first checked. */
export const DEFAULT_TABLER_PASSES = 2;

export const STAFF_PASSES_NOT_YET_ACTIVE = 'Staff passes open to you once your status is Active.';

/**
 * Whether the user is "🆕" staff, who can't claim staff passes, enter the
 * staff pass lottery or join the alternate list (enforced server-side too).
 */
export function staffPassesNotYetActive(user: Pick<UserResponse, 'can_claim_staff_passes'> | null | undefined): boolean {
  return user?.can_claim_staff_passes === false;
}

export const MY_PASSES_PAST_SHOW_DAYS = 3;

/** Whether a show (`YYYY-MM-DD`) is recent or upcoming enough to list on a My Passes page. */
export function isRecentShow(showDate: string | null | undefined): boolean {
  if (!showDate) return true;
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - MY_PASSES_PAST_SHOW_DAYS);
  return showDate >= formatDateValue(cutoff);
}

// The backend allows each DJ one on-air pass pair giveaway per show within
// this window (one DJ shift); see PassService.giveaway_pass.
export const DJ_SHOW_GIVEAWAY_WINDOW_HOURS = 4;

// The pass pair this DJ already gave away for the show within the window, if
// any. Names are compared ignoring case and surrounding spaces.
export function findRecentDjGiveaway<T extends Pick<PassResponse, 'given_away_by_dj' | 'given_away_at'>>(
  passes: T[],
  djName: string,
  now: Date = new Date(),
): T | undefined {
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

// Whether the DJ named djName may still correct this pass pair's winner: they
// gave it away (names compared ignoring case and surrounding spaces), within
// DJ_SHOW_GIVEAWAY_WINDOW_HOURS, and the show isn't closed or past its planned
// close time (in the studio's local time). The backend checks the same rules.
export function canDjEditWinner(
  pass: Pick<PassResponse, 'status' | 'given_away_by_dj' | 'given_away_at'>,
  show: Pick<ShowResponse, 'status' | 'planned_close_date' | 'planned_close_time'>,
  djName: string,
  now: Date = new Date(),
): boolean {
  const name = djName.trim().toLowerCase();
  if (pass.status !== 'given_away' || !name || !pass.given_away_at) return false;
  if (pass.given_away_by_dj?.trim().toLowerCase() !== name) return false;
  const windowMs = DJ_SHOW_GIVEAWAY_WINDOW_HOURS * 60 * 60 * 1000;
  if (now.getTime() - new Date(pass.given_away_at).getTime() >= windowMs) return false;
  if (show.status === 'closed') return false;
  if (show.planned_close_date && show.planned_close_time) {
    const [y, m, d] = show.planned_close_date.split('-').map(Number);
    const [h, min] = show.planned_close_time.split(':').map(Number);
    if (now >= new Date(y, m - 1, d, h, min)) return false;
  }
  return true;
}

export const WHEELCHAIR_ACCESSIBLE_LABELS: Record<WheelchairAccessible, string> = {
  yes: 'Yes',
  no: 'No',
  unknown: 'Unknown',
};

export const VENUE_TYPE_LABELS: Record<VenueType, string> = {
  music: 'Music Venue',
  movie_theater: 'Movie Theater',
};

export const AGE_RESTRICTION_LABELS: Record<AgeRestriction, string> = {
  all_ages: 'All Ages',
  '18+': '18+',
  '21+': '21+',
};

export const MOVIE_RATING_LABELS: Record<MovieRating, string> = {
  G: 'G',
  PG: 'PG',
  'PG-13': 'PG-13',
  R: 'R',
  'NC-17': 'NC-17',
  NR: 'Not Rated',
};

interface RatedShow {
  venue: { venue_type: VenueType };
  age_restriction: AgeRestriction | null;
  movie_rating: MovieRating | null;
}

// Shows at a movie theater have a movie rating instead of an age restriction
export const isMovieShow = (show: RatedShow): boolean =>
  show.venue.venue_type === 'movie_theater';

// The show's movie rating or age restriction, whichever its venue uses
export function formatShowRating(show: RatedShow): string {
  if (isMovieShow(show)) {
    return show.movie_rating ? MOVIE_RATING_LABELS[show.movie_rating] : 'Not set';
  }
  return show.age_restriction ? AGE_RESTRICTION_LABELS[show.age_restriction] : 'Not set';
}

// Louisiana's "LA" is left out: in a venue address it's Los Angeles
const US_STATE_CODES = new Set([
  'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'DC', 'FL', 'GA', 'HI', 'ID',
  'IL', 'IN', 'IA', 'KS', 'KY', 'ME', 'MD', 'MA', 'MI', 'MN', 'MS', 'MO',
  'MT', 'NE', 'NV', 'NH', 'NJ', 'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA',
  'RI', 'SC', 'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
]);

const US_STATE_NAME =
  /(?:^|\s)(?:alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|district of columbia|florida|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york|north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming)$/i;

const ZIP_CODE = /^\d{5}(?:-\d{4})?$/;

// Whether a venue address ends the way a full US postal address does, with a
// state and/or zip code ("…, Berkeley, CA 94704"). DJs read the address on
// air, so the venue form warns about these. Only the end of the address is
// checked, so a house number ("12345 Main St") or a street named after a
// state ("123 Washington St") doesn't count.
export function addressHasStateOrZip(address: string): boolean {
  // Lines and commas both separate the parts of an address
  const segments = address
    .split(/[\n,]/)
    .map((segment) => segment.trim())
    .filter(Boolean);
  if (segments.length > 0 && /^(?:usa?|united states(?: of america)?)\.?$/i.test(segments[segments.length - 1])) {
    segments.pop();
  }
  if (segments.length === 0) return false;

  const tokens = segments[segments.length - 1].replace(/\./g, '').split(/\s+/);
  const isOnlySegment = segments.length === 1;

  // A zip code is the last word, but never the first word of the address,
  // which is the house number
  if (ZIP_CODE.test(tokens[tokens.length - 1]) && !(isOnlySegment && tokens.length === 1)) {
    return true;
  }

  // A state comes after the street, so it's in a later part of the address
  // ("123 Main St, Berkeley CA") or at the end of a single-line one
  // ("123 Main St Berkeley CA"). Only a part that is just the state may be
  // lowercase ("Berkeley, ca"); otherwise a lowercase word is more likely
  // ordinary text ("Side door, around back in"). Without a comma a trailing
  // "NE" is more likely part of the street ("Main St NE").
  const last = tokens[tokens.length - 1];
  if (US_STATE_CODES.has(last.toUpperCase())) {
    const isUppercase = last === last.toUpperCase();
    if (!isOnlySegment && (tokens.length === 1 || isUppercase)) return true;
    if (isOnlySegment && tokens.length > 1 && isUppercase && last !== 'NE') return true;
  }
  return !isOnlySegment && US_STATE_NAME.test(segments[segments.length - 1]);
}

// Venue name as it sorts, ignoring a leading "The " so that "The Fox Theater"
// sorts as "Fox Theater".
export function venueSortName(name: string): string {
  return name.trim().replace(/^the\s+/i, '');
}

// Compares venue names for sorting, ignoring a leading "The " and case.
export function compareVenueNames(a: string, b: string): number {
  return venueSortName(a).localeCompare(venueSortName(b), undefined, { sensitivity: 'base' });
}

/** Join names as "A", "A and B" or "A, B and C". */
export const joinNames = (names: string[]): string =>
  names.length <= 1
    ? names.join('')
    : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
