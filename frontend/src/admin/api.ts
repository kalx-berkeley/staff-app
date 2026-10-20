import apiClient, { handleAPIError } from '../common/api';
import type {
  AuditLogFilters,
  AuditLogItem,
  ImpersonateRequest,
  JobRunResult,
  DjQuizDeadline,
  JobStatus,
  ShortLink,
  ShortLinkRequest,
  UserListItem,
} from './types';

/**
 * KALX Staff Admin API methods. Ending an impersonation is in common/api.ts,
 * since every sub-site offers it.
 */
export const adminAPI = {
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

  /** Staging only. */
  startImpersonation: async (request: ImpersonateRequest): Promise<void> => {
    try {
      await apiClient.post('/admin/impersonate', request);
    } catch (error) {
      return handleAPIError(error);
    }
  },

  /** Active users to impersonate. Staging only. */
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

  /** Short links, for site admins. */
  listShortLinks: async (): Promise<ShortLink[]> => {
    try {
      const response = await apiClient.get<ShortLink[]>('/short-links');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  createShortLink: async (request: ShortLinkRequest): Promise<ShortLink> => {
    try {
      const response = await apiClient.post<ShortLink>('/short-links', request);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  updateShortLink: async (id: number, request: ShortLinkRequest): Promise<ShortLink> => {
    try {
      const response = await apiClient.put<ShortLink>(`/short-links/${id}`, request);
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  deleteShortLink: async (id: number): Promise<void> => {
    try {
      await apiClient.delete(`/short-links/${id}`);
    } catch (error) {
      return handleAPIError(error);
    }
  },

  // The Staff Directory's DJ Quiz deadlines (site admins)
  listDjQuizDeadlines: async (): Promise<DjQuizDeadline[]> => {
    try {
      const response = await apiClient.get<DjQuizDeadline[]>('/directory/admin/dj-quiz-deadlines');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  setDjQuizDeadline: async (year: number, deadline: string): Promise<DjQuizDeadline> => {
    try {
      const response = await apiClient.put<DjQuizDeadline>(
        `/directory/admin/dj-quiz-deadlines/${year}`,
        { deadline },
      );
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  deleteDjQuizDeadline: async (year: number): Promise<void> => {
    try {
      await apiClient.delete(`/directory/admin/dj-quiz-deadlines/${year}`);
    } catch (error) {
      return handleAPIError(error);
    }
  },
};
