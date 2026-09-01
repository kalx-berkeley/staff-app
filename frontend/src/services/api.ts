/**
 * API client service for communicating with the backend REST API.
 * 
 * This module provides typed API methods for all backend endpoints,
 * organized by resource (shows, venues, passes, users, autocomplete).
 * All methods handle errors consistently and return typed responses.
 * 
 * @module api
 */

import axios, { AxiosError, AxiosInstance } from 'axios';
import type {
  SpecialtyShowCreate,
  SpecialtyShowUpdate,
  SpecialtyShowResponse,
  SelfPreAssignmentData,
  PromoterCreate,
  PromoterUpdate,
  PromoterResponse,
  VenueCreate,
  VenueUpdate,
  VenueResponse,
  ShowCreate,
  ShowUpdate,
  ShowResponse,
  ShowSummary,
  ShowBand,
  ShowBandCreate,
  MusicBrainzArtist,
  ShowListParams,
  ShowSearchParams,
  ShowAttempt,
  PassResponse,
  GiveawayData,
  PreAssignmentData,
  WinnerReleaseData,
  UserResponse,
  PromotionsStaffProfile,
  StaffProfile,
  SyncResult,
  JobStatus,
  JobRunResult,
  SeedResult,
  WinnerEligibility,
  ImpersonateRequest,
  UserListItem,
  NotificationPreferences,
  AuditLogItem,
  AuditLogFilters,
  AutoCloseScheduleItem,
  LotteryScheduleItem,
  APIError,
  LotteryStatus,
  LotteryEntryResponse,
  StaffLotteryEntryCreate,
  DJLotteryEntryCreate,
} from '../types';

/**
 * Axios instance configured with base URL and authentication settings.
 * Includes credentials for cookie-based authentication with mod_auth_openidc.
 */
const apiClient: AxiosInstance = axios.create({
  baseURL: '/pass-giveaway/api',
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Include cookies for authentication
});

// Key used to store a single 401 diagnostic record across the redirect.
export const AUTH_DIAG_KEY = 'kalx_auth_diag';

// Redirect to app root on 401 so Apache mod_auth_openidc can re-initiate OAuth.
// DJ-network unauthenticated users always get 200 (role="dj"), never 401.
//
// If a 401 is already recorded in sessionStorage it means we already redirected
// once and are still looping — stop redirecting and let the error propagate so
// React renders normally and the diagnostic banner can display the captured info.
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const alreadyCapturing = sessionStorage.getItem(AUTH_DIAG_KEY);
      if (!alreadyCapturing) {
        try {
          sessionStorage.setItem(
            AUTH_DIAG_KEY,
            JSON.stringify({
              url: error.config?.url ?? '(unknown)',
              method: (error.config?.method ?? 'GET').toUpperCase(),
              body: error.response?.data,
              fromPath: window.location.pathname,
              at: new Date().toISOString(),
            })
          );
        } catch { /* sessionStorage unavailable — skip diagnostic */ }
        window.location.href = '/pass-giveaway/';
        return new Promise(() => {}); // prevent error propagation during navigation
      }
      // Already captured — propagate so React can render the diagnostic banner.
      return Promise.reject(error);
    }
    return Promise.reject(error);
  }
);

/**
 * Handles API errors consistently across all endpoints.
 * Extracts error details from Axios errors and throws them.
 * 
 * @param error - The error object from a failed API call
 * @throws {APIError} Structured error with detail message
 * @throws {Error} Generic error for non-Axios errors
 */
export const handleAPIError = (error: unknown): never => {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<APIError>;
    if (axiosError.response?.data) {
      throw axiosError.response.data;
    }
    throw new Error(axiosError.message || 'Network error occurred');
  }
  throw error;
};

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
  create: async (data: ShowCreate): Promise<ShowResponse> => {
    try {
      const response = await apiClient.post<ShowResponse>('/shows', data);
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
   * @param showId - Show ID
   * @param djName - Name of DJ who attempted the giveaway
   * @returns Promise resolving to created ShowAttempt
   */
  recordAttempt: async (showId: number, djName: string): Promise<ShowAttempt> => {
    try {
      const response = await apiClient.post<ShowAttempt>(`/shows/${showId}/attempt`, {
        dj_name: djName,
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

  getArtistWikipedia: async (artistId: string): Promise<{ extract: string | null; wikipedia_url: string | null }> => {
    try {
      const response = await apiClient.get<{ extract: string | null; wikipedia_url: string | null }>(
        `/shows/musicbrainz/artist/${artistId}/wikipedia`
      );
      return response.data;
    } catch {
      return { extract: null, wikipedia_url: null };
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
  claim: async (passId: number, data?: import('../types').ClaimData): Promise<PassResponse> => {
    try {
      const response = await apiClient.post<PassResponse>(`/passes/${passId}/claim`, data ?? {});
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Get current DJ's giveaway history.
   * Returns all passes given away by the authenticated DJ.
   * 
   * @returns Promise resolving to array of passes
   */
  getMyGiveaways: async (djName: string): Promise<PassResponse[]> => {
    try {
      const response = await apiClient.get<PassResponse[]>('/passes/my-giveaways', {
        params: { dj_name: djName },
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

  removePreassignment: async (passId: number, djName?: string): Promise<PassResponse> => {
    try {
      const response = await apiClient.delete<PassResponse>(
        `/passes/${passId}/preassign`,
        { params: djName ? { dj_name: djName } : undefined }
      );
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
 * Users API methods for profile management and authentication.
 */
export const usersAPI = {
  /**
   * Get current authenticated user information.
   * Returns email and role from Google OAuth via mod_auth_openidc.
   * 
   * @returns Promise resolving to user info
   */
  getMe: async (): Promise<UserResponse> => {
    try {
      const response = await apiClient.get<UserResponse>('/users/me');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Get current user's profile.
   * Returns promotions staff or staff member profile.
   * 
   * @returns Promise resolving to profile data
   */
  getProfile: async (): Promise<PromotionsStaffProfile | StaffProfile> => {
    try {
      const response = await apiClient.get<PromotionsStaffProfile | StaffProfile>(
        '/users/profile'
      );
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /**
   * Trigger Airtable user synchronization (admin only).
   * Syncs staff and promotions staff from Airtable to the database.
   *
   * @returns Promise resolving to sync results
   */
  sync: async (): Promise<SyncResult> => {
    try {
      const response = await apiClient.post<SyncResult>('/users/sync');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

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
};

/**
 * Autocomplete API methods for providing suggestions.
 */
export const autocompleteAPI = {
  /**
   * Get DJ names for autocomplete.
   * Returns distinct names of DJs who have given away passes.
   * 
   * @returns Promise resolving to array of DJ names
   */
  getDJNames: async (): Promise<string[]> => {
    try {
      const response = await apiClient.get<string[]>('/autocomplete/djs');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },
};

/**
 * Admin API methods (staging-only).
 */
export const adminAPI = {
  getSeedStatus: async (): Promise<{ seeded: boolean }> => {
    try {
      const response = await apiClient.get<{ seeded: boolean }>('/admin/seed-status');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  seedTestData: async (): Promise<SeedResult> => {
    try {
      const response = await apiClient.post<SeedResult>('/admin/seed-test-data');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  getJobStatuses: async (): Promise<JobStatus[]> => {
    try {
      const response = await apiClient.get<JobStatus[]>('/admin/job-statuses');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  triggerJob: async (jobId: string): Promise<JobRunResult> => {
    try {
      const response = await apiClient.post<JobRunResult>(`/admin/jobs/${jobId}/run`);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  startImpersonation: async (request: ImpersonateRequest): Promise<void> => {
    try {
      await apiClient.post('/admin/impersonate', request);
    } catch (error) {
      return handleAPIError(error);
    }
  },

  endImpersonation: async (): Promise<void> => {
    try {
      await apiClient.delete('/admin/impersonate');
    } catch (error) {
      return handleAPIError(error);
    }
  },

  listUsers: async (): Promise<UserListItem[]> => {
    try {
      const response = await apiClient.get<UserListItem[]>('/admin/users');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  getAuditLog: async (filters: AuditLogFilters = {}): Promise<AuditLogItem[]> => {
    try {
      const response = await apiClient.get<AuditLogItem[]>('/admin/audit-log', {
        params: filters,
      });
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  getAutoCloseSchedules: async (): Promise<AutoCloseScheduleItem[]> => {
    try {
      const response = await apiClient.get<AutoCloseScheduleItem[]>('/admin/auto-close-schedules');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  getLotterySchedules: async (): Promise<LotteryScheduleItem[]> => {
    try {
      const response = await apiClient.get<LotteryScheduleItem[]>('/admin/lottery-schedules');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  runLottery: async (showId: number): Promise<JobRunResult> => {
    try {
      const response = await apiClient.post<JobRunResult>(`/admin/lottery-schedules/${showId}/run`);
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
  checkWinner: async (venueId: number, phone: string, showId: number): Promise<WinnerEligibility> => {
    try {
      const response = await apiClient.get<WinnerEligibility>(`/venues/${venueId}/check-winner`, {
        params: { phone, show_id: showId },
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
  list: async (): Promise<SpecialtyShowResponse[]> => {
    try {
      const response = await apiClient.get<SpecialtyShowResponse[]>('/specialty-shows');
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
};

/**
 * Legacy paper-form import API — only functional when LEGACY_IMPORT_ENABLED=true on the backend.
 */
export const legacyImportAPI = {
  checkEnabled: async (): Promise<boolean> => {
    try {
      await apiClient.get('/legacy-import/enabled');
      return true;
    } catch {
      return false;
    }
  },

  listStaff: async (): Promise<{ id: number; name: string; email: string }[]> => {
    try {
      const response = await apiClient.get<{ id: number; name: string; email: string }[]>('/legacy-import/staff');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  importShow: async (data: {
    event_name: string;
    genre: string[];
    venue_id: number;
    show_date: string;
    show_time: string | null;
    show_start_date: string | null;
    on_air_description: string | null;
    caller_special_instructions: string | null;
    age_restriction: string;
    wheelchair_accessible: boolean;
    num_pass_pairs: number;
    co_announce: boolean;
    on_air_winners: { recipient_name: string; recipient_phone: string; recipient_email: string | null; given_away_by_dj: string | null }[];
    staff_passes: { staff_id: number; has_guest: boolean; guest_name: string | null }[];
  }): Promise<{ show_id: number; on_air_winners_created: number; staff_passes_claimed: number }> => {
    try {
      const response = await apiClient.post('/legacy-import/shows', data);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },
};

/**
 * Feedback API for submitting user feedback and bug reports.
 */
export const feedbackAPI = {
  submit: async (data: { page_url: string; message: string }): Promise<void> => {
    try {
      await apiClient.post('/users/feedback', data);
    } catch (error) {
      return handleAPIError(error);
    }
  },
};

/**
 * Export the axios instance for custom requests if needed.
 * Use the typed API methods above for standard operations.
 */
export default apiClient;
