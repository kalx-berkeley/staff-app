import { act, render, type RenderResult } from '@testing-library/react';
import type { ReactNode } from 'react';
import { AuthProvider } from '../common/contexts/AuthContext';

/**
 * Render `ui` inside act() and let the fetches its effects start (with mocked,
 * already-resolved APIs) settle before returning, so their state updates
 * don't land after the test ends and trigger React's "not wrapped in
 * act(...)" warning.
 */
export const renderAndSettle = async (ui: ReactNode): Promise<RenderResult> => {
  let result!: RenderResult;
  await act(async () => {
    result = render(ui);
  });
  return result;
};

/**
 * renderAndSettle inside AuthProvider, so its `usersAPI.getMe()` call settles
 * too. Mock `usersAPI.getMe` before calling.
 */
export const renderWithAuth = (ui: ReactNode): Promise<RenderResult> =>
  renderAndSettle(<AuthProvider>{ui}</AuthProvider>);
