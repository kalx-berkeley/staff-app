import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, screen, within } from '@testing-library/react';
import App from '../App';
import { renderWithAuth } from '../test/render';
import { usersAPI } from '../common/api';
import type { UserResponse } from '../common/types';

vi.mock('../common/api', () => ({
  AUTH_DIAG_KEY: 'kalx_auth_diag',
  usersAPI: { getMe: vi.fn() },
  impersonationAPI: { end: vi.fn() },
  feedbackAPI: { submit: vi.fn() },
  handleAPIError: vi.fn(),
}));

vi.mock('./api', () => ({
  adminAPI: {
    getAutoCloseSchedules: vi.fn().mockResolvedValue([]),
    getLotterySchedules: vi.fn().mockResolvedValue([]),
    getSeedStatus: vi.fn().mockResolvedValue({ seeded: false }),
  },
  showsAPI: { listDeleted: vi.fn().mockResolvedValue([]) },
  venuesAPI: { listDeleted: vi.fn().mockResolvedValue([]) },
  legacyImportAPI: { checkEnabled: vi.fn().mockResolvedValue(false) },
}));

// A department head who isn't promotions staff
const siteAdmin = (overrides: Partial<UserResponse> = {}): UserResponse => ({
  email: 'head@example.com',
  role: 'staff',
  is_dj_network: false,
  is_station_office_network: false,
  is_department_head: true,
  is_site_admin: true,
  profile: { id: 1, name: 'Hal Head', phone: '', dj_name: null, is_sublist_dj: false },
  ...overrides,
});

const renderAt = async (path: string, me: UserResponse) => {
  window.history.pushState({}, '', path);
  vi.mocked(usersAPI.getMe).mockResolvedValue(me);
  await renderWithAuth(<App />);
};

describe('Promotions → Admin', () => {
  // Load the lazy Promotions chunk up front, so the first test doesn't wait on it
  beforeAll(async () => {
    await import('./promotions');
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
    window.history.pushState({}, '', '/');
  });

  it('is open to site admins who are not promotions staff, with only an Admin link', async () => {
    await renderAt('/pass-giveaway/promotions/admin', siteAdmin());

    expect(await screen.findByRole('heading', { name: 'Admin' })).toBeInTheDocument();
    const nav = screen.getByRole('navigation');
    expect(within(nav).getByRole('link', { name: 'Admin' })).toBeInTheDocument();
    expect(within(nav).queryByRole('link', { name: 'Shows' })).not.toBeInTheDocument();
  });

  it('hides the Admin link while impersonating, but the page still works', async () => {
    await renderAt(
      '/pass-giveaway/promotions/admin',
      siteAdmin({
        is_staging: true,
        email: 'staff@example.com',
        real_email: 'head@example.com',
        impersonating_email: 'staff@example.com',
      }),
    );

    expect(await screen.findByRole('heading', { name: 'Admin' })).toBeInTheDocument();
    const nav = screen.getByRole('navigation');
    expect(within(nav).queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument();
  });
});
