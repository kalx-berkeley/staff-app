import type { UserResponse } from '../common/types';

// Staging-only: lets a staff member with active Sublist DJ status access the
// DJ view, ahead of this being rolled out to production.
export function isStagingSublistDjStaff(user: Pick<UserResponse, 'role' | 'is_staging' | 'profile'> | null | undefined): boolean {
  return !!user?.is_staging && user.role === 'staff' && !!user.profile?.is_sublist_dj;
}
