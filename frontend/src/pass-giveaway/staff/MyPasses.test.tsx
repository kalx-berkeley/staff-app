import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import MyPasses from './MyPasses';
import { alternatesAPI, passesAPI } from '../api';
import type { MyAlternateEntry, PassResponse } from '../types';
import { formatDateValue } from '../../common/utils';

const auth = vi.hoisted(() => ({ isSublistDj: false }));

vi.mock('../api', () => ({
  passesAPI: {
    getStaffMyClaims: vi.fn().mockResolvedValue([]),
    getStaffMyGiveaways: vi.fn().mockResolvedValue([]),
  },
  lotteryAPI: {
    getMyEntries: vi.fn().mockResolvedValue([]),
  },
  alternatesAPI: {
    getMyEntries: vi.fn(),
    leave: vi.fn(),
  },
}));

vi.mock('../../common/contexts/authHooks', () => ({
  useAuth: () => ({
    user: {
      email: 'me@example.com',
      role: 'staff',
      is_dj_network: false,
      is_station_office_network: false,
      profile: {
        name: 'Me',
        phone: '555-0000',
        dj_name: auth.isSublistDj ? 'DJ Me' : null,
        is_sublist_dj: auth.isSublistDj,
      },
    },
    loading: false,
    error: null,
    refetchUser: vi.fn(),
  }),
}));

const entry: MyAlternateEntry = {
  outcome_pending: false,
  id: 4,
  show_id: 9,
  staff_id: 1,
  staff_name: 'Me',
  staff_phone: null,
  staff_email: null,
  position: 3,
  has_guest: true,
  guest_name: 'Pal',
  guest_fallback: 'attend_alone' as const,
  source: 'joined',
  priority_at: '2024-01-01T00:00:00Z',
  show_event_name: 'Big Show',
  show_date: '2099-05-01',
  show_venue_name: 'The Hall',
};

describe('Staff MyPasses — alternate lists', () => {
  beforeEach(() => {
    vi.mocked(alternatesAPI.getMyEntries).mockReset();
    vi.mocked(alternatesAPI.leave).mockReset();
  });

  it('hides the section when the user is not waiting anywhere', async () => {
    vi.mocked(alternatesAPI.getMyEntries).mockResolvedValue([]);
    render(<BrowserRouter><MyPasses /></BrowserRouter>);
    await waitFor(() => expect(alternatesAPI.getMyEntries).toHaveBeenCalled());
    expect(screen.queryByText('Alternate Lists')).not.toBeInTheDocument();
  });

  it('shows a held outcome instead of the queue position and Leave button', async () => {
    vi.mocked(alternatesAPI.getMyEntries).mockResolvedValue([{ ...entry, outcome_pending: true }]);

    render(<BrowserRouter><MyPasses /></BrowserRouter>);

    expect(
      await screen.findByText("The show has closed. You'll get an email with the outcome.")
    ).toBeInTheDocument();
    expect(screen.queryByText('Ahead of you:')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /leave list/i })).not.toBeInTheDocument();
  });

  it('lists entries with position and lets the user leave', async () => {
    vi.mocked(alternatesAPI.getMyEntries)
      .mockResolvedValueOnce([entry])
      .mockResolvedValue([]);
    vi.mocked(alternatesAPI.leave).mockResolvedValue(undefined);

    render(<BrowserRouter><MyPasses /></BrowserRouter>);

    expect(await screen.findByText('Alternate #3')).toBeInTheDocument();
    expect(screen.getByText('Big Show')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /leave list/i }));
    await waitFor(() => expect(alternatesAPI.leave).toHaveBeenCalledWith(9));
    await waitFor(() => expect(screen.queryByText('Alternate #3')).not.toBeInTheDocument());
  });
});

const daysFromToday = (days: number) => {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return formatDateValue(d);
};

const makePass = (overrides: Partial<PassResponse>): PassResponse => ({
  id: 1,
  show_id: 1,
  pass_type: 'pair',
  status: 'given_away',
  recipient_name: 'Caller Name',
  recipient_phone: '5105551234',
  recipient_email: null,
  given_away_by_dj: 'DJ Me',
  given_away_at: null,
  staff_id: null,
  staff_name: null,
  staff_phone: null,
  staff_email: null,
  claimed_at: null,
  has_guest: false,
  guest_name: null,
  guest_fallback: 'attend_alone' as const,
  guest_of_pass_id: null,
  preassigned_dj: null,
  preassigned_date: null,
  preassigned_specialty_show_id: null,
  preassigned_specialty_show_name: null,
  show_event_name: 'Show',
  show_date: daysFromToday(0),
  show_venue_name: 'The Hall',
  ...overrides,
});

describe('Staff MyPasses — past shows and winner details', () => {
  beforeEach(() => {
    auth.isSublistDj = true;
    vi.mocked(alternatesAPI.getMyEntries).mockResolvedValue([]);
  });

  afterEach(() => {
    auth.isSublistDj = false;
    vi.mocked(passesAPI.getStaffMyClaims).mockResolvedValue([]);
    vi.mocked(passesAPI.getStaffMyGiveaways).mockResolvedValue([]);
  });

  const mockOldAndRecentPasses = () => {
    vi.mocked(passesAPI.getStaffMyClaims).mockResolvedValue([
      makePass({ id: 1, pass_type: 'staff', status: 'claimed', show_event_name: 'Old Claim', show_date: daysFromToday(-8) }),
      makePass({ id: 2, pass_type: 'staff', status: 'claimed', show_event_name: 'Recent Claim', show_date: daysFromToday(-7) }),
    ]);
    vi.mocked(passesAPI.getStaffMyGiveaways).mockResolvedValue([
      makePass({ id: 3, show_event_name: 'Old Giveaway', show_date: daysFromToday(-10) }),
      makePass({ id: 4, show_event_name: 'New Giveaway', show_date: daysFromToday(2) }),
      makePass({ id: 5, status: 'available', preassigned_dj: 'DJ Me', show_event_name: 'Old Preassigned', show_date: daysFromToday(-9) }),
      makePass({ id: 6, status: 'available', preassigned_dj: 'DJ Me', show_event_name: 'Recent Preassigned', show_date: daysFromToday(-6) }),
      // A multi-day show's end date is recent, but the pass is for its first day
      makePass({ id: 7, status: 'available', preassigned_dj: 'DJ Me', show_event_name: 'Old Day Preassigned', show_date: daysFromToday(1), preassigned_date: daysFromToday(-8) }),
    ]);
  };

  it('hides passes for shows more than 7 days ago', async () => {
    mockOldAndRecentPasses();

    render(<BrowserRouter><MyPasses /></BrowserRouter>);

    expect(await screen.findByText('Recent Claim')).toBeInTheDocument();
    expect(await screen.findByText('New Giveaway')).toBeInTheDocument();
    expect(screen.getByText('Recent Preassigned')).toBeInTheDocument();
    expect(screen.queryByText('Old Claim')).not.toBeInTheDocument();
    expect(screen.queryByText('Old Giveaway')).not.toBeInTheDocument();
    expect(screen.queryByText('Old Preassigned')).not.toBeInTheDocument();
    expect(screen.queryByText('Old Day Preassigned')).not.toBeInTheDocument();
  });

  it('shows older passes when asked', async () => {
    mockOldAndRecentPasses();

    render(<BrowserRouter><MyPasses /></BrowserRouter>);

    fireEvent.click(await screen.findByLabelText('Show shows more than 7 days ago'));

    expect(await screen.findByText('Old Claim')).toBeInTheDocument();
    expect(screen.getByText('Old Giveaway')).toBeInTheDocument();
    expect(screen.getByText('Old Preassigned')).toBeInTheDocument();
    expect(screen.getByText('Old Day Preassigned')).toBeInTheDocument();
    expect(screen.getByText('Recent Claim')).toBeInTheDocument();
  });

  it('leaves out the older shows control when nothing is hidden', async () => {
    vi.mocked(passesAPI.getStaffMyClaims).mockResolvedValue([
      makePass({ id: 2, pass_type: 'staff', status: 'claimed', show_event_name: 'Recent Claim', show_date: daysFromToday(-7) }),
    ]);

    render(<BrowserRouter><MyPasses /></BrowserRouter>);

    expect(await screen.findByText('Recent Claim')).toBeInTheDocument();
    expect(screen.queryByLabelText(/more than 7 days ago/)).not.toBeInTheDocument();
  });

  it("doesn't show the winner's name or phone number", async () => {
    vi.mocked(passesAPI.getStaffMyGiveaways).mockResolvedValue([
      makePass({ show_event_name: 'New Giveaway' }),
    ]);

    render(<BrowserRouter><MyPasses /></BrowserRouter>);

    expect(await screen.findByText('New Giveaway')).toBeInTheDocument();
    expect(screen.queryByText('Caller Name')).not.toBeInTheDocument();
    expect(screen.queryByText(/555-1234/)).not.toBeInTheDocument();
  });

  it("shows a talk show member's history even when they aren't a Sublist DJ", async () => {
    auth.isSublistDj = false;
    vi.mocked(passesAPI.getStaffMyGiveaways).mockResolvedValue([
      makePass({ show_event_name: 'Talk Giveaway', given_away_by_dj: 'Morning Report' }),
    ]);

    render(<BrowserRouter><MyPasses /></BrowserRouter>);

    expect(await screen.findByText('Talk Giveaway')).toBeInTheDocument();
    expect(screen.getByText('My Giveaway History')).toBeInTheDocument();
    expect(screen.getByText('Morning Report')).toBeInTheDocument();
  });

  it('leaves out the history section for someone with none', async () => {
    auth.isSublistDj = false;
    render(<BrowserRouter><MyPasses /></BrowserRouter>);

    await waitFor(() => expect(passesAPI.getStaffMyGiveaways).toHaveBeenCalled());
    expect(screen.queryByText('My Giveaway History')).not.toBeInTheDocument();
  });
});
