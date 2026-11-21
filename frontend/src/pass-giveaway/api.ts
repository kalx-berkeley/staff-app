/**
 * Radio Pass Giveaway API methods, organized by resource. The shared client
 * and common endpoints (users, feedback) are in common/api.ts.
 *
 * @module api
 */

import apiClient, { handleAPIError } from '../common/api';
import { pageContextQuery } from '../common/pageTime';
import { SWITCH_HEADER, addOnAirHeaders } from './dj/onAirHeaders';
import type {
  AgeCheck,
  GiveawayCreditItem,
  AlternateEntry,
  AlternateJoinRequest,
  AlternateQueue,
  ArtistInfo,
  AutoCloseScheduleItem,
  ClaimData,
  DJLotteryEntryCreate,
  DescriptionAnalysis,
  DjLeave,
  DjSuggestion,
  GenrePreferences,
  GiveawayData,
  Identity,
  IdentityChoice,
  IdentitySchedule,
  JobRunResult,
  LotteryEntryResponse,
  LotteryScheduleItem,
  LotteryStatus,
  MusicBrainzArtist,
  MyAlternateEntry,
  MyIdentity,
  MyLotteryEntryResponse,
  MySpecialtyShowResponse,
  NotificationPreferences,
  OnAirInfo,
  GuestFallback,
  PassResponse,
  PreAssignmentData,
  PromoterCreate,
  PromoterResponse,
  PromoterUpdate,
  PromotionsStaffOption,
  SeedResult,
  SelfPreAssignmentData,
  ShowAttempt,
  ShowBand,
  ShowBandCreate,
  ShowCreate,
  ShowSplitCreate,
  SplitShowsResponse,
  StaffPassClaimant,
  ShowListParams,
  ShowResponse,
  ShowSearchParams,
  ShowSummary,
  ShowUpdate,
  SpecialtyShowCreate,
  SpecialtyShowOwnerInfo,
  SpecialtyShowResponse,
  SpecialtyShowCategory,
  SpecialtyShowUpdate,
  SpinMatch,
  StaffLotteryEntryCreate,
  VenueCreate,
  VenueResponse,
  VenueUpdate,
  WinnerEligibility,
  WinnerReleaseData,
  WinnerUpdateData,
} from './types';

// Name the DJ studio guest on the backend's log lines, and tell it about an
// early switch to the next on-air slot (see dj/onAirHeaders.ts).
apiClient.interceptors.request.use(addOnAirHeaders);

/**
 * Shows API methods for managing show records.
 * Includes CRUD operations, status transitions, and search.
 */
export const showsAPI = {
  /**
   * List all shows filtered by user role on backend.
   * Draft shows only visible to promotions staff.
   *
   * @param params - Optional date range params (date_from, date_to as YYYY-MM-DD strings)
   * @returns Promise resolving to array of shows
   */
  list: async (params?: ShowListParams): Promise<ShowSummary[]> => {
    try {
      const response = await apiClient.get<ShowSummary[]>('/shows', { params });
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Search shows with freetext and filters.
   * Applies role-based visibility filtering.
   * 
   * @param params - Search parameters (freetext, venue_id, artist, genre)
   * @returns Promise resolving to array of matching shows
   */
  search: async (params: ShowSearchParams): Promise<ShowSummary[]> => {
    try {
      const response = await apiClient.get<ShowSummary[]>('/shows/search', {
        params,
      });
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Get a single show by ID.
   * 
   * @param id - Show ID
   * @returns Promise resolving to show details
   */
  get: async (id: number): Promise<ShowResponse> => {
    try {
      const response = await apiClient.get<ShowResponse>(`/shows/${id}`);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Create a new show (promotions staff only).
   * Automatically sets status to "draft" and creates passes.
   * 
   * @param data - Show creation data
   * @returns Promise resolving to created show
   */
  /**
   * List the Active staff who can get a staff pass, for the show form's staff
   * winner picker (promotions staff only).
   */
  /**
   * List the staff who can get a staff pass. With `includeNew`, also lists
   * "🆕" staff, who can be given a tabler pass.
   */
  listStaffPassClaimants: async (includeNew = false): Promise<StaffPassClaimant[]> => {
    try {
      const response = await apiClient.get<StaffPassClaimant[]>('/shows/staff-pass-claimants', {
        params: includeNew ? { include_new: true } : undefined,
      });
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * The upcoming 21+ shows the signed-in staff member is, or might be, too
   * young for, by show ID. Shows they're old enough for are left out.
   */
  getMyAgeChecks: async (): Promise<Record<number, AgeCheck>> => {
    try {
      const response = await apiClient.get<Record<number, AgeCheck>>('/shows/my-age-checks');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  create: async (data: ShowCreate): Promise<ShowResponse> => {
    try {
      const response = await apiClient.post<ShowResponse>('/shows', data);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Create a show at a venue that gives staff passes for a different date, as
   * two shows: the on-air show with the pass pairs and the staff show with the
   * staff passes (promotions staff only).
   */
  createSplit: async (data: ShowSplitCreate): Promise<SplitShowsResponse> => {
    try {
      const response = await apiClient.post<SplitShowsResponse>('/shows/split', data);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Update an existing show (promotions staff only).
   * 
   * @param id - Show ID
   * @param data - Show update data
   * @returns Promise resolving to updated show
   */
  update: async (id: number, data: ShowUpdate): Promise<ShowResponse> => {
    try {
      const response = await apiClient.put<ShowResponse>(`/shows/${id}`, data);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Publish a show (promotions staff only).
   * Transitions show from draft to published status.
   * 
   * @param id - Show ID
   * @returns Promise resolving to published show
   */
  publish: async (id: number): Promise<ShowResponse> => {
    try {
      const response = await apiClient.post<ShowResponse>(`/shows/${id}/publish`);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Close a show (promotions staff only).
   * Transitions show from published to closed status.
   * Prevents further pass operations.
   *
   * @param id - Show ID
   * @returns Promise resolving to closed show
   */
  close: async (id: number): Promise<ShowResponse> => {
    try {
      const response = await apiClient.post<ShowResponse>(`/shows/${id}/close`);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Unpublish a show (promotions staff only).
   * Transitions show from published back to draft status.
   *
   * @param id - Show ID
   * @returns Promise resolving to unpublished show
   */
  unpublish: async (id: number): Promise<ShowResponse> => {
    try {
      const response = await apiClient.post<ShowResponse>(`/shows/${id}/unpublish`);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Send a closed show's held emails to staff with a +1 and alternates
   * (promotions staff only).
   *
   * @param id - Show ID
   * @returns Promise resolving to the updated show
   */
  sendCloseNotifications: async (id: number): Promise<ShowResponse> => {
    try {
      const response = await apiClient.post<ShowResponse>(`/shows/${id}/send-close-notifications`);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },  markPassesCalledIn: async (id: number): Promise<ShowResponse> => {
    try {
      const response = await apiClient.post<ShowResponse>(`/shows/${id}/passes-called-in`);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },  undoPassesCalledIn: async (id: number): Promise<ShowResponse> => {
    try {
      const response = await apiClient.delete<ShowResponse>(`/shows/${id}/passes-called-in`);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Reopen a closed show (promotions staff only).
   * Transitions show from closed back to published status.
   * Only allowed if the show date has not yet passed.
   *
   * @param id - Show ID
   * @returns Promise resolving to reopened show
   */
  reopen: async (id: number): Promise<ShowResponse> => {
    try {
      const response = await apiClient.post<ShowResponse>(`/shows/${id}/reopen`);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Delete a show entirely (promotions staff only).
   *
   * @param id - Show ID
   * @returns Promise resolving when deletion is complete
   */
  delete: async (id: number): Promise<void> => {
    try {
      await apiClient.delete(`/shows/${id}`);
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Record a failed giveaway attempt for a show (DJ only).
   *
   * The server credits it to whoever is on air.
   *
   * @param showId - Show ID
   * @param visitId - The giveaway page visit, for KALX Staff Analytics
   * @returns Promise resolving to created ShowAttempt
   */
  recordAttempt: async (showId: number, visitId?: string | null): Promise<ShowAttempt> => {
    try {
      const response = await apiClient.post<ShowAttempt>(`/shows/${showId}/attempt`, {
        ...(visitId ? { visit_id: visitId } : {}),
      });
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Suggest a genre for the given event name.
   * Checks local DB history then falls back to MusicBrainz.
   * Returns null if no suggestion is available.
   *
   * @param eventName - The event/artist name to look up
   * @returns Promise resolving to suggested genre string or null
   */
  listGenres: async (): Promise<string[]> => {
    try {
      const response = await apiClient.get<string[]>('/shows/genres');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Analyze an on-air description for language that is not value neutral.
   * Detects praise of the band, promotion of the show, calls to action and
   * use of "ticket" where "pass" is required. Advisory only.
   *
   * @param text - The on-air description as typed by the user
   * @returns Promise resolving to the analysis findings and summary
   */
  analyzeDescription: async (text: string): Promise<DescriptionAnalysis> => {
    try {
      const response = await apiClient.post<DescriptionAnalysis>(
        '/shows/analyze-description',
        { text }
      );
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  suggestGenre: async (eventName: string): Promise<string[]> => {
    try {
      const response = await apiClient.get<{ genres: string[] }>('/shows/suggest-genre', {
        params: { event_name: eventName },
      });
      return response.data.genres ?? [];
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * List all soft-deleted shows (promotions staff only).
   *
   * @returns Promise resolving to list of deleted shows
   */
  listDeleted: async (): Promise<ShowResponse[]> => {
    try {
      const response = await apiClient.get<ShowResponse[]>('/shows/deleted');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Restore a soft-deleted show to draft status (promotions staff only).
   *
   * @param id - Show ID
   * @returns Promise resolving to restored show
   */
  undelete: async (id: number): Promise<ShowResponse> => {
    try {
      const response = await apiClient.post<ShowResponse>(`/shows/${id}/undelete`);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  updateBands: async (showId: number, bands: ShowBandCreate[]): Promise<ShowBand[]> => {
    try {
      const response = await apiClient.put<ShowBand[]>(`/shows/${showId}/bands`, bands);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  searchMusicBrainz: async (name: string): Promise<MusicBrainzArtist[]> => {
    try {
      const response = await apiClient.get<MusicBrainzArtist[]>('/shows/musicbrainz/search', {
        params: { name },
      });
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /** The artist's Wikipedia extract and MusicBrainz links, for the band popup. */
  getArtistInfo: async (artistId: string): Promise<ArtistInfo> => {
    try {
      const response = await apiClient.get<ArtistInfo>(
        `/shows/musicbrainz/artist/${artistId}/info`
      );
      return { ...response.data, links: response.data.links ?? [] };
    } catch {
      return { extract: null, wikipedia_url: null, links: [] };
    }
  },
};

/**
 * Venues API methods for managing venue records.
 */
export const venuesAPI = {
  /**
   * List all venues ordered by name.
   * 
   * @returns Promise resolving to array of venues
   */
  list: async (): Promise<VenueResponse[]> => {
    try {
      const response = await apiClient.get<VenueResponse[]>('/venues');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * List promotions department staff, for owner-picker autocompletes.
   *
   * @returns Promise resolving to array of promotions staff options
   */
  listPromotionsStaff: async (): Promise<PromotionsStaffOption[]> => {
    try {
      const response = await apiClient.get<PromotionsStaffOption[]>('/venues/promotions-staff');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Get a single venue by ID.
   * 
   * @param id - Venue ID
   * @returns Promise resolving to venue details
   */
  get: async (id: number): Promise<VenueResponse> => {
    try {
      const response = await apiClient.get<VenueResponse>(`/venues/${id}`);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Create a new venue (promotions staff only).
   * Venue names must be unique.
   * 
   * @param data - Venue creation data
   * @returns Promise resolving to created venue
   */
  create: async (data: VenueCreate): Promise<VenueResponse> => {
    try {
      const response = await apiClient.post<VenueResponse>('/venues', data);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Update an existing venue (promotions staff only).
   *
   * @param id - Venue ID
   * @param data - Venue update data
   * @returns Promise resolving to updated venue
   */
  update: async (id: number, data: VenueUpdate): Promise<VenueResponse> => {
    try {
      const response = await apiClient.put<VenueResponse>(`/venues/${id}`, data);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Soft-delete a venue (promotions staff only).
   *
   * @param id - Venue ID
   */
  delete: async (id: number): Promise<void> => {
    try {
      await apiClient.delete(`/venues/${id}`);
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * List all soft-deleted venues (promotions staff only).
   *
   * @returns Promise resolving to list of deleted venues
   */
  listDeleted: async (): Promise<VenueResponse[]> => {
    try {
      const response = await apiClient.get<VenueResponse[]>('/venues/deleted');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Restore a soft-deleted venue (promotions staff only).
   *
   * @param id - Venue ID
   * @returns Promise resolving to restored venue
   */
  undelete: async (id: number): Promise<VenueResponse> => {
    try {
      const response = await apiClient.post<VenueResponse>(`/venues/${id}/undelete`);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  uploadLogo: async (id: number, file: File): Promise<VenueResponse> => {
    try {
      const form = new FormData();
      form.append('file', file);
      const response = await apiClient.post<VenueResponse>(`/venues/${id}/logo`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  deleteLogo: async (id: number): Promise<VenueResponse> => {
    try {
      const response = await apiClient.delete<VenueResponse>(`/venues/${id}/logo`);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },
};

/**
 * Passes API methods for managing pass operations.
 * Includes giveaways, claims, attempts, and pre-assignments.
 */
export const passesAPI = {
  /**
   * Get all passes for a show.
   * Includes pass pairs and staff passes with their status.
   * 
   * @param showId - Show ID
   * @returns Promise resolving to array of passes
   */
  getForShow: async (showId: number): Promise<PassResponse[]> => {
    try {
      const response = await apiClient.get<PassResponse[]>(`/shows/${showId}/passes`);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Give away a pass pair (DJ only).
   * Records winner information and marks pass as given_away.
   *
   * @param passId - Pass ID
   * @param data - Giveaway data with recipient and DJ info
   * @returns Promise resolving to updated pass
   */
  giveaway: async (passId: number, data: GiveawayData): Promise<PassResponse> => {
    try {
      const response = await apiClient.post<PassResponse>(
        `/passes/${passId}/giveaway`,
        data
      );
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Claim a staff pass (staff only).
   * Associates pass with staff member's profile.
   * 
   * @param passId - Pass ID
   * @returns Promise resolving to claimed pass
   */
  claim: async (passId: number, data?: ClaimData): Promise<PassResponse> => {
    try {
      const response = await apiClient.post<PassResponse>(`/passes/${passId}/claim`, data ?? {});
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /** Add a +1 guest to your own claimed staff pass. */
  addGuest: async (
    passId: number,
    data: { guest_name: string | null; guest_fallback: GuestFallback }
  ): Promise<PassResponse> => {
    try {
      const response = await apiClient.post<PassResponse>(`/passes/${passId}/guest`, data);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /** Correct the name of the +1 guest on your own claimed staff pass. */
  updateGuestName: async (passId: number, guestName: string | null): Promise<PassResponse> => {
    try {
      const response = await apiClient.patch<PassResponse>(`/passes/${passId}/guest`, {
        guest_name: guestName,
      });
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /** Remove a +1 guest from a claimed staff pass, whether seated or waiting. */
  removeGuest: async (passId: number): Promise<PassResponse> => {
    try {
      const response = await apiClient.delete<PassResponse>(`/passes/${passId}/guest`);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Get the winner the on-air DJ recorded, including their email, to correct it.
   * Only answers while the persona or show credited with it is on air, within 4 hours.
   */
  getWinnerForEdit: async (passId: number): Promise<PassResponse> => {
    try {
      const response = await apiClient.get<PassResponse>(`/passes/${passId}/winner`);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /** Correct the winner the on-air DJ recorded (same rules as getWinnerForEdit). */
  updateWinner: async (passId: number, data: WinnerUpdateData): Promise<PassResponse> => {
    try {
      const response = await apiClient.patch<PassResponse>(`/passes/${passId}/winner`, data);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * The on-air identity's giveaways and pre-assigned passes (or, after an
   * early switch, the next identity's).
   *
   * @param switchTo - Ask as the next slot starting at this time (ISO), to
   *   count its passes before switching; the server honours it only in the
   *   last 10 minutes before that slot.
   */
  getMyGiveaways: async (switchTo?: string): Promise<PassResponse[]> => {
    try {
      const response = await apiClient.get<PassResponse[]>('/passes/my-giveaways', {
        headers: switchTo ? { [SWITCH_HEADER]: switchTo } : undefined,
      });
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  getStaffMyGiveaways: async (): Promise<PassResponse[]> => {
    try {
      const response = await apiClient.get<PassResponse[]>('/passes/staff/my-giveaways');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Get the current staff member's currently claimed staff passes, across all shows.
   * Available to any staff member or promotions staff.
   *
   * @returns Promise resolving to array of claimed staff passes
   */
  getStaffMyClaims: async (): Promise<PassResponse[]> => {
    try {
      const response = await apiClient.get<PassResponse[]>('/passes/staff/my-claims');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Set pre-assignment for a pass pair (promotions staff only).
   * Assigns pass to specific DJ for a specific date.
   * 
   * @param passId - Pass ID
   * @param data - Pre-assignment data with DJ name and date
   * @returns Promise resolving to updated pass
   */
  setPreassignment: async (
    passId: number,
    data: PreAssignmentData
  ): Promise<PassResponse> => {
    try {
      const response = await apiClient.post<PassResponse>(
        `/passes/${passId}/preassign`,
        data
      );
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Remove pre-assignment from a pass pair (promotions staff only).
   * Makes pass available to any DJ.
   *
   * @param passId - Pass ID
   * @returns Promise resolving to updated pass
   */
  selfPreassign: async (passId: number, data: SelfPreAssignmentData): Promise<PassResponse> => {
    try {
      const response = await apiClient.post<PassResponse>(
        `/passes/${passId}/preassign/self`,
        data
      );
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * List what promotions can pre-assign a pass pair to: current staff
   * members' personas (inactive ones hidden), then the current shows.
   */
  getPreassignIdentities: async (): Promise<Identity[]> => {
    try {
      const response = await apiClient.get<Identity[]>('/passes/preassign/identities');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * List what the signed-in staff member can reserve on-air pass pairs for
   * (their own personas and their shows), each with its schedule.
   */
  getMyPreassignIdentities: async (): Promise<MyIdentity[]> => {
    try {
      const response = await apiClient.get<MyIdentity[]>('/passes/preassign/my-identities');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * When a persona or show is on the schedule in the next ~8 weeks.
   *
   * Used to narrow the pre-assignment date picker, and to warn about a date
   * the schedule doesn't show it on.
   *
   * @param identity - A persona or a show
   */
  getPreassignSchedule: async (identity: IdentityChoice): Promise<IdentitySchedule> => {
    try {
      const response = await apiClient.get<IdentitySchedule>('/passes/preassign/schedule', {
        params: identity.persona_id != null
          ? { persona_id: identity.persona_id }
          : { specialty_show_id: identity.specialty_show_id },
      });
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Get the current or upcoming leave of absence of the staff member holding a persona.
   *
   * @returns Promise resolving to the leave dates, or null when there's none
   */
  getPreassignLeave: async (personaId: number): Promise<DjLeave | null> => {
    try {
      const response = await apiClient.get<DjLeave | null>('/passes/preassign/leave', {
        params: { persona_id: personaId },
      });
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Suggest DJs/specialty shows scheduled on-air on a given date, for the
   * "Suggest DJs by date" pre-assignment flow.
   *
   * @param date - Date to check, as a YYYY-MM-DD string
   * @returns Promise resolving to an array of suggestions
   */
  getSuggestionsByDate: async (date: string): Promise<DjSuggestion[]> => {
    try {
      const response = await apiClient.get<DjSuggestion[]>(
        '/passes/preassign/suggest-by-date',
        { params: { date } }
      );
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Suggest Sublist DJs (and their specialty shows) whose genre preferences
   * overlap a show's genres, for the "Suggest DJs by genre" pre-assignment flow.
   *
   * @param showId - Show ID
   * @returns Promise resolving to an array of suggestions
   */
  getSuggestionsByGenre: async (showId: number): Promise<DjSuggestion[]> => {
    try {
      const response = await apiClient.get<DjSuggestion[]>(
        '/passes/preassign/suggest-by-genre',
        { params: { show_id: showId } }
      );
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Clothespin: reserve one unclaimed pass pair of a show for whoever is on
   * air, for today (DJ studio only).
   *
   * @param showId - Show ID
   * @returns Promise resolving to the reserved pass pair
   */
  clothespin: async (showId: number): Promise<PassResponse> => {
    try {
      const response = await apiClient.post<PassResponse>(`/shows/${showId}/clothespin`);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  removePreassignment: async (passId: number): Promise<PassResponse> => {
    try {
      const response = await apiClient.delete<PassResponse>(`/passes/${passId}/preassign`);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Release a claimed staff pass (staff only).
   * Unlinks the pass from the staff member and makes it available again.
   * Blocked when the show is closed.
   *
   * @param passId - Pass ID
   * @returns Promise resolving to updated pass
   */
  releaseClaim: async (passId: number): Promise<PassResponse> => {
    try {
      const response = await apiClient.delete<PassResponse>(`/passes/${passId}/claim`);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Claim one of a co-announce show's tabler passes (Publicity members only).
   *
   * @param showId - Show ID
   * @returns Promise resolving to the claimed tabler pass
   */
  claimTablerPass: async (showId: number): Promise<PassResponse> => {
    try {
      const response = await apiClient.post<PassResponse>(
        `/shows/${showId}/tabler-passes/claim`
      );
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Give a staff member one of a show's tabler passes (promotions only).
   *
   * @param showId - Show ID
   * @param staffId - Staff member ID
   * @returns Promise resolving to the assigned tabler pass
   */
  assignTablerPass: async (showId: number, staffId: number): Promise<PassResponse> => {
    try {
      const response = await apiClient.post<PassResponse>(
        `/shows/${showId}/tabler-passes/assign`,
        { staff_id: staffId }
      );
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Search for pass winners by phone number (DJ only).
   * Returns all pass pairs won by callers with the given phone number.
   *
   * @param phone - Phone number to search for
   * @returns Promise resolving to array of passes
   */
  searchByPhone: async (phone: string): Promise<PassResponse[]> => {
    try {
      const response = await apiClient.get<PassResponse[]>('/passes/search-by-phone', {
        params: { phone },
      });
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Release an on-air winner from a pass (DJ only).
   * Makes the pass available for re-giveaway and notifies venue owners.
   * Blocked when the show is closed.
   *
   * @param passId - Pass ID
   * @param data - Release data with reason and optional identity fields
   * @returns Promise resolving to updated pass
   */
  releaseWinner: async (passId: number, data: WinnerReleaseData): Promise<PassResponse> => {
    try {
      const response = await apiClient.post<PassResponse>(
        `/passes/${passId}/release-winner`,
        data
      );
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },
};

/**
 * The current user's pass giveaway preferences: pass emails and liked genres.
 */
export const preferencesAPI = {
  /**
   * Get current user's notification preferences.
   * Creates default preferences (email enabled) if none exist yet.
   *
   * @returns Promise resolving to notification preferences
   */
  getNotificationPreferences: async (): Promise<NotificationPreferences> => {
    try {
      const response = await apiClient.get<NotificationPreferences>(
        '/users/notification-preferences'
      );
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Update current user's notification preferences.
   *
   * @param prefs - Updated preferences
   * @returns Promise resolving to updated notification preferences
   */
  updateNotificationPreferences: async (
    prefs: NotificationPreferences
  ): Promise<NotificationPreferences> => {
    try {
      const response = await apiClient.put<NotificationPreferences>(
        '/users/notification-preferences',
        prefs
      );
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Get current user's genre preferences.
   * Creates a default (empty) list if none exist yet.
   *
   * @returns Promise resolving to genre preferences
   */
  getGenrePreferences: async (): Promise<GenrePreferences> => {
    try {
      const response = await apiClient.get<GenrePreferences>('/users/genre-preferences');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Update current user's genre preferences.
   *
   * @param prefs - Updated genre preferences
   * @returns Promise resolving to updated genre preferences
   */
  updateGenrePreferences: async (prefs: GenrePreferences): Promise<GenrePreferences> => {
    try {
      const response = await apiClient.put<GenrePreferences>(
        '/users/genre-preferences',
        prefs
      );
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },
};

/**
 * On-air DJ schedule API methods, backed by the cached Spinitron schedule.
 */
export const onAirAPI = {
  /**
   * Who is on air now and next.
   *
   * @returns Promise resolving to the current and next on-air identity
   */
  getCurrent: async (): Promise<OnAirInfo> => {
    try {
      const response = await apiClient.get<OnAirInfo>('/dj/on-air');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Get spins currently matching a show with passes to give away.
   *
   * Returns every current match on every call, including ones already
   * returned by a previous poll or to another open tab — see dismissSpinMatch.
   * The query arguments are only for the access logs (see pageTime).
   *
   * @returns Promise resolving to the list of current matches (usually empty)
   */
  getSpinMatches: async (): Promise<SpinMatch[]> => {
    try {
      const response = await apiClient.get<SpinMatch[]>(`/dj/spin-matches?${pageContextQuery()}`);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Mark one spin/show match as dismissed so it stops being returned by
   * getSpinMatches, including to any other open DJ tab (as of its next poll).
   *
   * @param spinId - The Spinitron spin ID from the match
   * @param showId - The show ID from the match
   * @param action - Whether the DJ dismissed it or clicked through, for KALX Staff Analytics
   */
  dismissSpinMatch: async (
    spinId: number,
    showId: number,
    action?: 'dismissed' | 'clicked',
  ): Promise<void> => {
    try {
      await apiClient.post(`/dj/spin-matches/${spinId}/dismiss`, null, {
        params: { show_id: showId, ...(action ? { action } : {}) },
      });
    } catch (error) {
      return handleAPIError(error);
    }
  },
};

/**
 * Pass giveaway admin API methods. The app-wide admin tools are in admin/api.ts.
 */
export const adminAPI = {
  /** Staging only. */
  getSeedStatus: async (): Promise<{ seeded: boolean }> => {
    try {
      const response = await apiClient.get<{ seeded: boolean }>('/pass-giveaway/admin/seed-status');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /** Staging only. */
  seedTestData: async (): Promise<SeedResult> => {
    try {
      const response = await apiClient.post<SeedResult>('/pass-giveaway/admin/seed-test-data');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  getAutoCloseSchedules: async (): Promise<AutoCloseScheduleItem[]> => {
    try {
      const response = await apiClient.get<AutoCloseScheduleItem[]>('/pass-giveaway/admin/auto-close-schedules');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  getLotterySchedules: async (): Promise<LotteryScheduleItem[]> => {
    try {
      const response = await apiClient.get<LotteryScheduleItem[]>('/pass-giveaway/admin/lottery-schedules');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Pass pairs given away in the last *days* days, newest first; with
   * *unattributed*, only those credited to no one.
   */
  getGiveaways: async (unattributed: boolean, days: number): Promise<GiveawayCreditItem[]> => {
    try {
      const response = await apiClient.get<GiveawayCreditItem[]>('/pass-giveaway/admin/giveaways', {
        params: { unattributed, days },
      });
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /** What a giveaway can be credited to: current staff personas, then current shows. */
  getCreditIdentities: async (): Promise<Identity[]> => {
    try {
      const response = await apiClient.get<Identity[]>('/pass-giveaway/admin/credit-identities');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /** Re-credit a giveaway to a persona or a show, or to no one (null). */
  recreditGiveaway: async (passId: number, identity: Identity | null): Promise<GiveawayCreditItem> => {
    try {
      const response = await apiClient.put<GiveawayCreditItem>(
        `/pass-giveaway/admin/giveaways/${passId}/credit`,
        {
          persona_id: identity?.persona_id ?? null,
          specialty_show_id: identity?.specialty_show_id ?? null,
        },
      );
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  runLottery: async (showId: number): Promise<JobRunResult> => {
    try {
      const response = await apiClient.post<JobRunResult>(
        `/pass-giveaway/admin/lottery-schedules/${showId}/run`,
      );
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },
};

/**
 * Passes check-winner API.
 */
export const venuePassesAPI = {
  /** excludePassId ignores that pass's own winner, when correcting their phone. */
  checkWinner: async (
    venueId: number,
    phone: string,
    showId: number,
    excludePassId?: number,
  ): Promise<WinnerEligibility> => {
    try {
      const response = await apiClient.get<WinnerEligibility>(`/venues/${venueId}/check-winner`, {
        params: { phone, show_id: showId, exclude_pass_id: excludePassId },
      });
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },
};

/**
 * Venues (my venues) API
 */
export const venuesMyAPI = {
  listMy: async (): Promise<VenueResponse[]> => {
    try {
      const response = await apiClient.get<VenueResponse[]>('/venues/my');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },
};

/**
 * Promoters API methods for managing promoter records.
 */
export const promotersAPI = {
  list: async (): Promise<PromoterResponse[]> => {
    try {
      const response = await apiClient.get<PromoterResponse[]>('/promoters');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  get: async (id: number): Promise<PromoterResponse> => {
    try {
      const response = await apiClient.get<PromoterResponse>(`/promoters/${id}`);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  create: async (data: PromoterCreate): Promise<PromoterResponse> => {
    try {
      const response = await apiClient.post<PromoterResponse>('/promoters', data);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  update: async (id: number, data: PromoterUpdate): Promise<PromoterResponse> => {
    try {
      const response = await apiClient.put<PromoterResponse>(`/promoters/${id}`, data);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  delete: async (id: number): Promise<void> => {
    try {
      await apiClient.delete(`/promoters/${id}`);
    } catch (error) {
      return handleAPIError(error);
    }
  },

  undelete: async (id: number): Promise<PromoterResponse> => {
    try {
      const response = await apiClient.post<PromoterResponse>(`/promoters/${id}/undelete`);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },
};

export const specialtyShowsAPI = {
  /**
   * Current shows, and retired ones too if `includeRetired`. Both kinds
   * (Specialty Music Shows and Talk & Info Shows) unless `category` picks one.
   */
  list: async (
    includeRetired = false,
    category?: SpecialtyShowCategory,
  ): Promise<SpecialtyShowResponse[]> => {
    try {
      const params: Record<string, string | boolean> = {};
      if (includeRetired) params.include_retired = true;
      if (category) params.category = category;
      const response = await apiClient.get<SpecialtyShowResponse[]>('/specialty-shows', {
        params: Object.keys(params).length ? params : undefined,
      });
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  listMy: async (): Promise<SpecialtyShowResponse[]> => {
    try {
      const response = await apiClient.get<SpecialtyShowResponse[]>('/specialty-shows/my');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  listMine: async (): Promise<MySpecialtyShowResponse[]> => {
    try {
      const response = await apiClient.get<MySpecialtyShowResponse[]>('/specialty-shows/mine');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  get: async (id: number): Promise<SpecialtyShowResponse> => {
    try {
      const response = await apiClient.get<SpecialtyShowResponse>(`/specialty-shows/${id}`);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  create: async (data: SpecialtyShowCreate): Promise<SpecialtyShowResponse> => {
    try {
      const response = await apiClient.post<SpecialtyShowResponse>('/specialty-shows', data);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  update: async (id: number, data: SpecialtyShowUpdate): Promise<SpecialtyShowResponse> => {
    try {
      const response = await apiClient.put<SpecialtyShowResponse>(`/specialty-shows/${id}`, data);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  delete: async (id: number): Promise<void> => {
    try {
      await apiClient.delete(`/specialty-shows/${id}`);
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /** Retire a show that has ended, or make a retired one current again. */
  setRetired: async (id: number, retired: boolean): Promise<SpecialtyShowResponse> => {
    try {
      const response = await apiClient.post<SpecialtyShowResponse>(
        `/specialty-shows/${id}/${retired ? 'retire' : 'unretire'}`,
      );
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  getUpcomingTitles: async (): Promise<string[]> => {
    try {
      const response = await apiClient.get<string[]>('/specialty-shows/upcoming-titles');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * The personas a music show's DJ editor offers: current staff members'
   * (inactive ones hidden), plus the show's own DJs.
   */
  getDjOptions: async (showId?: number): Promise<Identity[]> => {
    try {
      const response = await apiClient.get<Identity[]>('/specialty-shows/dj-options', {
        params: showId !== undefined ? { show_id: showId } : undefined,
      });
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  getDjHistory: async (id: number): Promise<string[]> => {
    try {
      const response = await apiClient.get<string[]>(`/specialty-shows/${id}/dj-history`);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  listStaffEmails: async (): Promise<SpecialtyShowOwnerInfo[]> => {
    try {
      const response = await apiClient.get<SpecialtyShowOwnerInfo[]>('/specialty-shows/staff-emails');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },
};

export const lotteryAPI = {
  getStatus: async (showId: number): Promise<LotteryStatus> => {
    try {
      const response = await apiClient.get<LotteryStatus>(`/shows/${showId}/lottery`);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  enterStaff: async (showId: number, data?: StaffLotteryEntryCreate): Promise<LotteryEntryResponse> => {
    try {
      const response = await apiClient.post<LotteryEntryResponse>(`/shows/${showId}/lottery/enter/staff`, data ?? {});
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  enterDJ: async (showId: number, data: DJLotteryEntryCreate): Promise<LotteryEntryResponse> => {
    try {
      const response = await apiClient.post<LotteryEntryResponse>(`/shows/${showId}/lottery/enter/dj`, data);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  withdrawStaff: async (showId: number): Promise<void> => {
    try {
      await apiClient.delete(`/shows/${showId}/lottery/staff_entry`);
    } catch (error) {
      return handleAPIError(error);
    }
  },

  withdrawDJ: async (showId: number): Promise<void> => {
    try {
      await apiClient.delete(`/shows/${showId}/lottery/dj_entry`);
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Get the current staff member's pending lottery entries, across all shows.
   * Includes both staff pass-lottery entries and (for Sublist DJs) DJ pass-pair
   * lottery entries.
   */
  getMyEntries: async (): Promise<MyLotteryEntryResponse[]> => {
    try {
      const response = await apiClient.get<MyLotteryEntryResponse[]>('/shows/lottery/my-entries');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },
};

/**
 * Staff-pass alternate queue API. Staff join once every staff pass is held by a
 * staff member; freed passes go to waiting alternates automatically.
 */
export const alternatesAPI = {
  getQueue: async (showId: number): Promise<AlternateQueue> => {
    try {
      const response = await apiClient.get<AlternateQueue>(`/shows/${showId}/alternates`);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  join: async (showId: number, data: AlternateJoinRequest): Promise<AlternateEntry> => {
    try {
      const response = await apiClient.post<AlternateEntry>(`/shows/${showId}/alternates`, data);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  updateMine: async (showId: number, data: AlternateJoinRequest): Promise<AlternateEntry> => {
    try {
      const response = await apiClient.patch<AlternateEntry>(`/shows/${showId}/alternates/me`, data);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  leave: async (showId: number): Promise<void> => {
    try {
      await apiClient.delete(`/shows/${showId}/alternates/me`);
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /** Promotions staff only: remove someone from the queue (they are emailed). */
  remove: async (showId: number, entryId: number): Promise<void> => {
    try {
      await apiClient.delete(`/shows/${showId}/alternates/${entryId}`);
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /** The current staff member's waiting alternate entries, across all shows. */
  getMyEntries: async (): Promise<MyAlternateEntry[]> => {
    try {
      const response = await apiClient.get<MyAlternateEntry[]>('/shows/alternates/my-entries');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },
};
