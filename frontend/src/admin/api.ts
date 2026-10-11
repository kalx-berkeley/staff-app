import apiClient, { handleAPIError } from '../common/api';
import type {
  AuditLogFilters,
  AuditLogItem,
  ImpersonateRequest,
  JobRunResult,
  JobStatus,
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
};
