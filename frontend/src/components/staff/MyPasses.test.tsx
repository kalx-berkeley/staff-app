import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import MyPasses from './MyPasses';
import { alternatesAPI } from '../../services/api';
import type { MyAlternateEntry } from '../../types';

vi.mock('../../services/api', () => ({
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

vi.mock('../../contexts/authHooks', () => ({
  useAuth: () => ({
    user: {
      email: 'me@example.com',
      role: 'staff',
      is_dj_network: false,
      is_station_office_network: false,
      profile: { name: 'Me', phone: '555-0000', dj_name: null, is_sublist_dj: false },
    },
    loading: false,
    error: null,
    refetchUser: vi.fn(),
  }),
}));

const entry: MyAlternateEntry = {
  id: 4,
  show_id: 9,
  staff_id: 1,
  staff_name: 'Me',
  position: 3,
  has_guest: true,
  guest_name: 'Pal',
  only_attend_with_guest: false,
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
