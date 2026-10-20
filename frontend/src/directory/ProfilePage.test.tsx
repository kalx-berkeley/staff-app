import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, within, cleanup, fireEvent } from '@testing-library/react';
import App from '../App';
import { renderWithAuth } from '../test/render';
import { directoryAPI } from './api';
import { usersAPI } from '../common/api';
import type { Eligibility, Profile } from './types';
import type { UserResponse } from '../common/types';

vi.mock('../common/api', () => ({
  AUTH_DIAG_KEY: 'kalx_auth_diag',
  usersAPI: { getMe: vi.fn() },
  handleAPIError: vi.fn(),
}));

vi.mock('./api', () => ({
  directoryAPI: {
    list: vi.fn(),
    photoUrl: vi.fn(() => null),
    getProfile: vi.fn(),
    updateProfile: vi.fn(),
    uploadPhoto: vi.fn(),
    searchPersonas: vi.fn(),
    resolvePersona: vi.fn(),
  },
}));

const staffUser: UserResponse = {
  email: 'zed@example.com',
  role: 'staff',
  is_dj_network: false,
  is_station_office_network: false,
  profile: { id: 5, name: 'Zed Zulu', phone: '', dj_name: 'DJ Zed', is_sublist_dj: true },
};

const ELIGIBILITY: Eligibility = {
  eligible: false,
  unmet: 1,
  unavailable: 0,
  eligible_until: null,
  next_workform_note: "Keep reporting 6 h a month: October's workform counts from November 1.",
  sublist: { met: true, summary: 'On the DJ sublist' },
  leave: { met: true, summary: 'Not on leave', loa_start: null, loa_end: null },
  shift: {
    met: false,
    summary: 'No qualifying shift in May–Jul 2026',
    previous_quarter: 'May–Jul 2026',
    current_quarter: 'Aug–Oct 2026',
    min_minutes: 90,
    playlists: [
      {
        id: 77,
        start: '2026-06-03T17:00:00Z',
        end: '2026-06-03T19:00:00Z',
        title: 'Take Five',
        minutes: 120,
        shift_minutes: null,
        counted: false,
        reason: 'specialty',
        quarter: 'previous',
        url: 'https://spinitron.com/KALX/pl/77/',
      },
    ],
    shifts_as_of: '2026-10-20T10:30:00Z',
  },
  workforms: {
    met: true,
    summary: 'Jul 6 h ✓, Aug 7 h ✓, Sep 6 h ✓',
    required_hours: 6,
    months: [
      {
        month: '2026-09',
        most_recent: true,
        met: true,
        counted_hours: 6,
        status: 'submitted',
        loa: false,
        departments: [{ department: 'Music', hours: 6, decision: null, counted: true }],
        pending_departments: [],
      },
    ],
  },
  quiz: {
    met: true,
    summary: '2026 quiz done',
    current_year: 2026,
    years: [2025, 2026],
    this_year_deadline: '2026-09-30',
    due: null,
    deadline_announced: true,
  },
};

const profile = (overrides: Partial<Profile> = {}): Profile => ({
  entry: {
    id: 5,
    name: 'Zed Zulu',
    pronouns: 'he/him',
    email: 'zed@example.com',
    phone: '(510) 555-0100',
    dj_name: 'DJ Zed',
    dj_personas: [{ id: 111, name: 'DJ Zed' }],
    departments: ['Music'],
    statuses: ['Active', 'Sublist DJ'],
    titles_and_roles: null,
    photo_version: null,
    on_leave: false,
    loa_start: null,
    loa_end: null,
    dj_quiz_years: [2025, 2026],
  },
  first_name: 'Zed',
  surname: 'Zulu',
  loa_start: '2025-01-01',
  loa_end: '2025-03-01',
  is_self: true,
  can_edit: false,
  eligibility: ELIGIBILITY,
  workforms: [
    {
      month: '2026-10',
      status: 'draft',
      reported_hours: 2,
      approved_hours: 0,
      is_late: false,
      loa: false,
    },
  ],
  ...overrides,
});

const renderProfile = async (path: string, user: UserResponse = staffUser) => {
  window.history.pushState({}, '', path);
  vi.mocked(usersAPI.getMe).mockResolvedValue(user);
  await renderWithAuth(<App />);
};

describe('ProfilePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('shows your own profile with the edit form greyed out', async () => {
    vi.mocked(directoryAPI.getProfile).mockResolvedValue(profile());
    await renderProfile('/directory/me');

    expect(await screen.findByRole('heading', { name: 'My profile' })).toBeInTheDocument();
    expect(directoryAPI.getProfile).toHaveBeenCalledWith('me');
    expect(screen.getByText('Jan 1, 2025 – Mar 1, 2025')).toBeInTheDocument();
    expect(screen.getByText('2025, 2026')).toBeInTheDocument();

    expect(screen.getByLabelText('First name')).toBeDisabled();
    expect(screen.getByLabelText('Phone')).toHaveValue('(510) 555-0100');
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled();
    expect(screen.getByRole('link', { name: 'this form' })).toHaveAttribute(
      'href',
      expect.stringContaining('docs.google.com/forms'),
    );

    expect(screen.getByText(/Not eligible yet: 1 of 5 requirements unmet/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'October 2026' })).toHaveAttribute(
      'href',
      '/workforms/month/2026-10',
    );
  });

  it('expands a requirement to show its evidence', async () => {
    vi.mocked(directoryAPI.getProfile).mockResolvedValue(profile());
    await renderProfile('/directory/me');

    const shift = (await screen.findByText('A DJ shift last quarter')).closest('details')!;
    expect(within(shift).getByRole('img', { name: 'Not met' })).toBeInTheDocument();
    fireEvent.click(within(shift).getByText('No qualifying shift in May–Jul 2026'));
    expect(shift).toHaveAttribute('open');
    expect(within(shift).getByRole('link', { name: 'Take Five' })).toHaveAttribute(
      'href',
      'https://spinitron.com/KALX/pl/77/',
    );
    expect(within(shift).getByText('Specialty show')).toBeInTheDocument();
  });

  it("lets site admins see someone else's profile", async () => {
    vi.mocked(directoryAPI.getProfile).mockResolvedValue(profile({ is_self: false }));
    await renderProfile('/directory/5/profile', {
      ...staffUser,
      email: 'boss@example.com',
      is_site_admin: true,
    });

    expect(await screen.findByRole('heading', { name: 'Zed Zulu’s profile' })).toBeInTheDocument();
    expect(directoryAPI.getProfile).toHaveBeenCalledWith(5);
    expect(screen.getByRole('link', { name: 'October 2026' })).toHaveAttribute(
      'href',
      '/workforms/staff/5/month/2026-10',
    );
  });

  it('shows why a profile can’t be loaded', async () => {
    vi.mocked(directoryAPI.getProfile).mockRejectedValue({
      detail: 'Only this staff member and site admins can see this profile',
    });
    await renderProfile('/directory/9/profile');

    expect(
      await screen.findByText('Only this staff member and site admins can see this profile'),
    ).toBeInTheDocument();
  });

  it('saves changes once editing is on', async () => {
    vi.mocked(directoryAPI.getProfile).mockResolvedValue(profile({ can_edit: true }));
    vi.mocked(directoryAPI.updateProfile).mockResolvedValue(
      profile({ can_edit: true, entry: { ...profile().entry, pronouns: 'they/them' } }),
    );
    await renderProfile('/directory/me');

    const pronouns = await screen.findByLabelText('Pronouns');
    expect(screen.queryByRole('link', { name: 'this form' })).not.toBeInTheDocument();
    fireEvent.change(pronouns, { target: { value: 'they/them' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    expect(await screen.findByText('Saved')).toBeInTheDocument();
    expect(directoryAPI.updateProfile).toHaveBeenCalledWith(5, {
      first_name: 'Zed',
      surname: 'Zulu',
      pronouns: 'they/them',
      phone: '(510) 555-0100',
      dj_persona_ids: [111],
    });
  });

  it('adds DJ names by searching or by pasting a Spinitron link', async () => {
    vi.mocked(directoryAPI.getProfile).mockResolvedValue(profile({ can_edit: true }));
    vi.mocked(directoryAPI.searchPersonas).mockResolvedValue([{ id: 222, name: 'Zed, Esq.' }]);
    vi.mocked(directoryAPI.resolvePersona).mockResolvedValue({ id: 333, name: 'Night Zed' });
    await renderProfile('/directory/me');

    const input = await screen.findByLabelText('Add a DJ name');
    fireEvent.change(input, { target: { value: 'ze' } });
    fireEvent.click(await screen.findByRole('button', { name: 'Zed, Esq.' }));
    expect(directoryAPI.searchPersonas).toHaveBeenCalledWith('ze');

    fireEvent.paste(input, {
      clipboardData: { getData: () => 'https://spinitron.com/KALX/dj/333/' },
    });
    const chips = await screen.findByRole('list', { name: 'Your DJ names' });
    expect(await within(chips).findByRole('link', { name: 'Night Zed' })).toBeInTheDocument();
    expect(within(chips).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      'DJ Zed×',
      'Zed, Esq.×',
      'Night Zed×',
    ]);

    fireEvent.click(within(chips).getByRole('button', { name: 'Remove DJ Zed' }));
    expect(within(chips).queryByRole('link', { name: 'DJ Zed' })).not.toBeInTheDocument();
  });
});
