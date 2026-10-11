import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, screen, within } from '@testing-library/react';
import App from '../App';
import { renderWithAuth } from '../test/render';
import { usersAPI } from '../common/api';
import type { UserResponse } from '../common/types';
import { SUBSITES } from '../subsites';
import { adminAPI } from './api';

vi.mock('../common/api', () => ({
  AUTH_DIAG_KEY: 'kalx_auth_diag',
  usersAPI: { getMe: vi.fn() },
  impersonationAPI: { end: vi.fn() },
  handleAPIError: vi.fn(),
}));

vi.mock('./api', () => ({
  adminAPI: {
    getJobStatuses: vi.fn(),
    triggerJob: vi.fn(),
    startImpersonation: vi.fn(),
    listUsers: vi.fn(),
    getAuditLog: vi.fn(),
  },
}));

const user = (overrides: Partial<UserResponse> = {}): UserResponse => ({
  email: 'head@example.com',
  role: 'staff',
  is_dj_network: false,
  is_station_office_network: false,
  is_department_head: true,
  is_admin: true,
  profile: { id: 1, name: 'Hal Head', phone: '', dj_name: null, is_sublist_dj: false },
  ...overrides,
});

const renderAdmin = async (me: UserResponse = user()) => {
  window.history.pushState({}, '', '/admin/');
  vi.mocked(usersAPI.getMe).mockResolvedValue(me);
  await renderWithAuth(<App />);
};

describe('KALX Staff Admin', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(adminAPI.getJobStatuses).mockResolvedValue([
      {
        id: 'airtable_user_sync',
        name: 'Sync users from Airtable',
        area: 'Common',
        can_run: true,
        last_run_at: null,
        next_run_at: null,
      },
      {
        id: 'workform_emails',
        name: 'Send workform reminder and review emails',
        area: 'KALX Workforms',
        can_run: false,
        last_run_at: null,
        next_run_at: null,
      },
    ]);
    vi.mocked(adminAPI.listUsers).mockResolvedValue([]);
  });

  afterEach(() => {
    cleanup();
    window.history.pushState({}, '', '/');
  });

  it('is offered only to admins', () => {
    const admin = SUBSITES.find((subsite) => subsite.basePath === '/admin')!;
    expect(admin.isAvailable(user())).toBe(true);
    expect(admin.isAvailable(user({ is_admin: false }))).toBe(false);
    expect(admin.isAvailable(null)).toBe(false);
  });

  it("lists every sub-site's jobs and runs one", async () => {
    vi.mocked(adminAPI.triggerJob).mockResolvedValue({ success: true, message: 'Synced 3 staff' });
    await renderAdmin();

    const row = (await screen.findByText('Sync users from Airtable')).closest('tr')!;
    expect(within(row).getByText('Common')).toBeInTheDocument();
    const emails = screen.getByText('Send workform reminder and review emails').closest('tr')!;
    expect(within(emails).getByText('Scheduled only')).toBeInTheDocument();

    fireEvent.click(within(row).getByRole('button', { name: 'Run Now' }));

    expect(await within(row).findByText('Synced 3 staff')).toBeInTheDocument();
    expect(adminAPI.triggerJob).toHaveBeenCalledWith('airtable_user_sync');
  });

  it('offers impersonation only on staging', async () => {
    await renderAdmin();
    await screen.findByText('Sync users from Airtable');
    expect(screen.queryByRole('heading', { name: 'User Impersonation' })).not.toBeInTheDocument();
    cleanup();

    await renderAdmin(user({ is_staging: true }));
    expect(await screen.findByRole('heading', { name: 'User Impersonation' })).toBeInTheDocument();
  });

  it('shows who an admin is impersonating, with a way to end it', async () => {
    await renderAdmin(user({ is_staging: true, email: 'amy@example.com', impersonating_email: 'amy@example.com' }));

    expect(await screen.findByText(/Viewing as amy@example.com/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'End impersonation' })).toBeInTheDocument();
  });
});
