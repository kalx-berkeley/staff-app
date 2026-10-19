import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, screen, within } from '@testing-library/react';
import App from '../App';
import { renderWithAuth } from '../test/render';
import { usersAPI } from '../common/api';
import type { UserResponse } from '../common/types';
import { SUBSITES } from '../subsites';
import { adminAPI } from './api';
import type { AuditLogItem } from './types';

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
    listShortLinks: vi.fn(),
  },
}));

const user = (overrides: Partial<UserResponse> = {}): UserResponse => ({
  email: 'head@example.com',
  role: 'staff',
  is_dj_network: false,
  is_station_office_network: false,
  is_department_head: true,
  is_site_admin: true,
  profile: { id: 1, name: 'Hal Head', phone: '', dj_name: null, is_sublist_dj: false },
  ...overrides,
});

const promotionsAdmin = (overrides: Partial<UserResponse> = {}): UserResponse =>
  user({
    email: 'promo@example.com',
    role: 'promotions',
    is_department_head: false,
    is_site_admin: false,
    is_promotions_admin: true,
    ...overrides,
  });

const auditEntry: AuditLogItem = {
  id: 1,
  occurred_at: '2026-10-17T12:00:00Z',
  event_type: 'workform_decision',
  area: 'KALX Workforms',
  actor_email: 'head@example.com',
  actor_role: 'staff',
  entity_type: null,
  entity_id: null,
  details: null,
};

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
    vi.mocked(adminAPI.listShortLinks).mockResolvedValue([]);
  });

  afterEach(() => {
    cleanup();
    window.history.pushState({}, '', '/');
  });

  it('is offered only to site admins and promotions admins', () => {
    const admin = SUBSITES.find((subsite) => subsite.basePath === '/admin')!;
    expect(admin.isAvailable(user())).toBe(true);
    expect(admin.isAvailable(user({ is_site_admin: false, is_promotions_admin: true }))).toBe(true);
    expect(admin.isAvailable(user({ is_site_admin: false }))).toBe(false);
    expect(admin.isAvailable(null)).toBe(false);
  });

  it('shows promotions admins the jobs without a way to run them', async () => {
    await renderAdmin(promotionsAdmin({ is_staging: true }));

    const row = (await screen.findByText('Sync users from Airtable')).closest('tr')!;
    expect(within(row).queryByRole('button', { name: 'Run Now' })).not.toBeInTheDocument();
    expect(screen.queryByRole('columnheader', { name: 'Action' })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'User Impersonation' })).not.toBeInTheDocument();
  });

  it('lets site admins filter the audit log by area', async () => {
    vi.mocked(adminAPI.getAuditLog).mockResolvedValue([auditEntry]);
    await renderAdmin();
    await screen.findByText('Sync users from Airtable');

    fireEvent.change(screen.getByRole('combobox', { name: 'Area' }), {
      target: { value: 'KALX Workforms' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Load' }));

    expect(await screen.findByRole('columnheader', { name: 'Area' })).toBeInTheDocument();
    expect(adminAPI.getAuditLog).toHaveBeenCalledWith(
      expect.objectContaining({ area: 'KALX Workforms' }),
    );
  });

  it("doesn't show promotions admins the audit log's area", async () => {
    vi.mocked(adminAPI.getAuditLog).mockResolvedValue([
      { ...auditEntry, area: 'Radio Pass Giveaway', event_type: 'show_created' },
    ]);
    await renderAdmin(promotionsAdmin());
    await screen.findByText('Sync users from Airtable');

    expect(screen.queryByRole('combobox', { name: 'Area' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Load' }));

    expect(await screen.findByText('show_created')).toBeInTheDocument();
    expect(screen.queryByRole('columnheader', { name: 'Area' })).not.toBeInTheDocument();
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

  it('shows the short links only to site admins', async () => {
    await renderAdmin();
    expect(await screen.findByRole('heading', { name: 'Short Links' })).toBeInTheDocument();
    cleanup();

    await renderAdmin(promotionsAdmin());
    await screen.findByText('Sync users from Airtable');
    expect(screen.queryByRole('heading', { name: 'Short Links' })).not.toBeInTheDocument();
    expect(adminAPI.listShortLinks).toHaveBeenCalledTimes(1);
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

  it('marks new students in the list of users to impersonate', async () => {
    vi.mocked(adminAPI.listUsers).mockResolvedValue([
      { email: 'nia@example.com', name: 'Nia New', role: 'staff', is_new: true },
    ]);
    await renderAdmin(user({ is_staging: true }));

    const input = await screen.findByRole('textbox', { name: 'User to impersonate' });
    fireEvent.change(input, { target: { value: 'nia' } });

    expect(await screen.findByText('Nia New 🆕 (nia@example.com)')).toBeInTheDocument();
  });

  it('picks the user to impersonate by typing part of their name', async () => {
    vi.mocked(adminAPI.listUsers).mockResolvedValue([
      { email: 'amy@example.com', name: 'Amy Adams', role: 'staff' },
      { email: 'bob@example.com', name: 'Bob Brown', role: 'promotions' },
    ]);
    // Rejecting keeps the component from reloading the page, which jsdom can't do
    vi.mocked(adminAPI.startImpersonation).mockRejectedValue({ detail: 'Stopped for test' });
    await renderAdmin(user({ is_staging: true }));

    const start = screen.getByRole('button', { name: 'Start Impersonation' });
    const input = await screen.findByRole('textbox', { name: 'User to impersonate' });
    fireEvent.change(input, { target: { value: 'amy' } });
    expect(start).toBeDisabled();
    fireEvent.mouseDown(screen.getByText('Amy Adams (amy@example.com)'));
    expect(input).toHaveValue('Amy Adams (amy@example.com)');

    fireEvent.click(start);

    expect(await screen.findByText('Stopped for test')).toBeInTheDocument();
    expect(adminAPI.startImpersonation).toHaveBeenCalledWith({
      email: 'amy@example.com',
      is_dj_network: false,
      is_station_office_network: false,
    });
  });
});
