/**
 * Authentication hooks for role-based access control.
 * 
 * @module authHooks
 */

import { useContext } from 'react';
import { AuthContext } from './authContext';
import type { UserRole } from '../types';

/**
 * Hook to access authentication context.
 * Must be used within an AuthProvider.
 * 
 * @returns Authentication context value
 * @throws Error if used outside AuthProvider
 */
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

/**
 * Hook to check if user has a specific role.
 * 
 * @param role - Role to check for
 * @returns True if user has the specified role
 */
export const useHasRole = (role: UserRole): boolean => {
  const { user } = useAuth();
  return user?.role === role;
};

/**
 * Hook to check if user has any of the specified roles.
 * 
 * @param roles - Array of roles to check
 * @returns True if user has any of the specified roles
 */
export const useHasAnyRole = (roles: UserRole[]): boolean => {
  const { user } = useAuth();
  return user ? roles.includes(user.role) : false;
};
