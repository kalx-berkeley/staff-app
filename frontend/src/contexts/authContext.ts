/**
 * Authentication context definition.
 * 
 * @module authContext
 */

import { createContext } from 'react';
import type { UserResponse } from '../types';

/**
 * Authentication context value type.
 */
export interface AuthContextType {
  /** Current authenticated user or null if not authenticated */
  user: UserResponse | null;
  /** Whether user data is currently being loaded */
  loading: boolean;
  /** Error message if user fetch failed */
  error: string | null;
  /** Function to manually refetch user data */
  refetchUser: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);
