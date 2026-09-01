/**
 * Authentication context for managing user authentication state.
 * 
 * Provides user information, loading state, and role-based access control
 * throughout the application. Fetches user data from Authelia on mount.
 * 
 * @module AuthContext
 */

import React, { useState, useEffect, ReactNode } from 'react';
import type { UserResponse } from '../types';
import { AuthContext } from './authContext';
import { usersAPI } from '../services/api';

/**
 * Props for AuthProvider component.
 */
interface AuthProviderProps {
  children: ReactNode;
}

/**
 * Authentication provider component.
 * Wraps the application to provide authentication context.
 * Automatically fetches user data on mount.
 * 
 * @param props - Component props
 * @returns Provider component
 */
export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  /**
   * Fetches current user data from the API.
   * Updates user state and handles errors.
   */
  const fetchUser = async () => {
    try {
      setLoading(true);
      setError(null);
      const userData = await usersAPI.getMe();
      setUser(userData);
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 401) {
        setUser(null);
      } else {
        console.error('Failed to fetch user:', err);
        setError('Failed to load user information');
        setUser(null);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUser();
  }, []);

  /**
   * Manually refetch user data.
   * Useful after profile updates or role changes.
   */
  const refetchUser = async () => {
    await fetchUser();
  };

  return (
    <AuthContext.Provider value={{ user, loading, error, refetchUser }}>
      {children}
    </AuthContext.Provider>
  );
};
