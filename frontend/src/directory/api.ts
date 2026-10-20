import apiClient, { handleAPIError } from '../common/api';
import type { DirectoryEntry, DjPersona, Profile, ProfileUpdate } from './types';

const call = async <T>(request: Promise<{ data: T }>): Promise<T> => {
  try {
    return (await request).data;
  } catch (error) {
    return handleAPIError(error);
  }
};

/**
 * Staff Directory API: contact details for every active staff member, and
 * profile pages.
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

  /** Your own profile, or (for site admins) anyone's. */
  getProfile: (staffId: number | 'me') =>
    call(apiClient.get<Profile>(`/directory/${staffId}/profile`)),

  updateProfile: (staffId: number, update: ProfileUpdate) =>
    call(apiClient.patch<Profile>(`/directory/${staffId}/profile`, update)),

  uploadPhoto: (staffId: number, photo: File) => {
    const form = new FormData();
    form.append('photo', photo);
    return call(apiClient.post<Profile>(`/directory/${staffId}/photo`, form));
  },

  /** Spinitron personas whose name contains `query`, for the DJ Name editor. */
  searchPersonas: (query: string) =>
    call(apiClient.get<DjPersona[]>('/directory/personas', { params: { q: query } })),

  /** The persona a pasted Spinitron DJ link points to. */
  resolvePersona: (url: string) =>
    call(apiClient.post<DjPersona>('/directory/personas/resolve', { url })),
};
