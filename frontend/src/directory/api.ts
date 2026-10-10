import apiClient, { handleAPIError } from '../common/api';
import type { DirectoryEntry } from './types';

/**
 * Staff Directory API: contact details for every active staff member.
 */
export const directoryAPI = {
  list: async (): Promise<DirectoryEntry[]> => {
    try {
      const response = await apiClient.get<DirectoryEntry[]>('/directory');
      return response.data;
    } catch (error) {
      return handleAPIError(error);
    }
  },

  photoUrl: (entry: DirectoryEntry, size: 'thumb' | 'medium'): string | null =>
    entry.photo_version
      ? `/api/directory/${entry.id}/photo?size=${size}&v=${encodeURIComponent(entry.photo_version)}`
      : null,
};
