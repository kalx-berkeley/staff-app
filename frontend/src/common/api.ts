/**
 * The shared API client used by every sub-site: the axios instance (with the
 * 401 redirect), error handling, and the endpoints common to all sub-sites.
 * Each sub-site's own endpoints live in its api.ts.
 *
 * @module api
 */

import axios, { AxiosError, AxiosInstance } from 'axios';
import type {
  APIError,
  PromotionsStaffProfile,
  StaffProfile,
  SyncResult,
  UserResponse,
} from './types';
import { currentSubsiteRoot } from '../subsites';

/**
 * Axios instance configured with base URL and authentication settings.
 * Includes credentials for cookie-based authentication with mod_auth_openidc.
 */
const apiClient: AxiosInstance = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Include cookies for authentication
});

// Key used to store a single 401 diagnostic record across the redirect.
export const AUTH_DIAG_KEY = 'kalx_auth_diag';

// Redirect to the current sub-site's root on 401 so Apache mod_auth_openidc can
// re-initiate OAuth.
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
        window.location.href = currentSubsiteRoot();
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
