import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import WinnerSearch from './WinnerSearch';
import { passesAPI } from '../../services/api';
import type { PassResponse } from '../../types';

vi.mock('../../services/api', () => ({
  passesAPI: {
    searchByPhone: vi.fn(),
    releaseWinner: vi.fn(),
  },
}));

vi.mock('../../contexts/authHooks', () => ({
  useAuth: vi.fn(),
}));

import { useAuth } from '../../contexts/authHooks';

const mockUseAuth = vi.mocked(useAuth);

const makePass = (overrides: Partial<PassResponse> = {}): PassResponse => ({
  id: 1,
  show_id: 10,
  pass_type: 'pair',
  status: 'given_away',
  recipient_name: 'Jane Winner',
  recipient_phone: '555-9999',
  recipient_email: null,
  given_away_by_dj: 'DJ Test',
  given_away_at: '2024-06-01T20:00:00',
  staff_id: null,
  staff_name: null,
  staff_phone: null,
  staff_email: null,
  claimed_at: null,
  has_guest: false,
  guest_name: null,
  only_attend_with_guest: false,
  guest_of_pass_id: null,
  preassigned_dj: null,
  preassigned_date: null,
  preassigned_specialty_show_id: null,
  preassigned_specialty_show_name: null,
  show_event_name: 'Test Band',
  show_date: '2024-06-01',
  show_venue_name: 'The Venue',
  show_status: 'published',
  ...overrides,
});

const renderWinnerSearch = () =>
  render(
    <BrowserRouter>
      <WinnerSearch />
    </BrowserRouter>
  );

describe('WinnerSearch', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      user: { email: 'staff@kalx.example', role: 'promotions', is_dj_network: false, is_station_office_network: false },
      loading: false,
      error: null,
      refetchUser: vi.fn(),
    });
  });

  it('renders the search form', () => {
    renderWinnerSearch();
    expect(screen.getByLabelText(/phone number/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /search/i })).toBeInTheDocument();
  });

  it('shows no-results message when search returns empty', async () => {
    vi.mocked(passesAPI.searchByPhone).mockResolvedValue([]);
    renderWinnerSearch();

    fireEvent.change(screen.getByLabelText(/phone number/i), { target: { value: '000-0000' } });
    fireEvent.click(screen.getByRole('button', { name: /search/i }));

    await waitFor(() => {
      expect(screen.getByText(/no pass winners found/i)).toBeInTheDocument();
    });
  });

  it('displays found pass details and show information', async () => {
    vi.mocked(passesAPI.searchByPhone).mockResolvedValue([makePass()]);
    renderWinnerSearch();

    fireEvent.change(screen.getByLabelText(/phone number/i), { target: { value: '555-9999' } });
    fireEvent.click(screen.getByRole('button', { name: /search/i }));

    await waitFor(() => {
      expect(screen.getByText('Test Band')).toBeInTheDocument();
      expect(screen.getByText('The Venue')).toBeInTheDocument();
      expect(screen.getByText('Jane Winner')).toBeInTheDocument();
      expect(screen.getByText('555-9999')).toBeInTheDocument();
    });
  });

  it('shows release form when pass is given_away and show is not closed', async () => {
    vi.mocked(passesAPI.searchByPhone).mockResolvedValue([makePass()]);
    renderWinnerSearch();

    fireEvent.change(screen.getByLabelText(/phone number/i), { target: { value: '555-9999' } });
    fireEvent.click(screen.getByRole('button', { name: /search/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /release passes/i })).toBeInTheDocument();
    });
  });

  it('hides passes for closed shows and shows no-releasable message', async () => {
    vi.mocked(passesAPI.searchByPhone).mockResolvedValue([makePass({ show_status: 'closed' })]);
    renderWinnerSearch();

    fireEvent.change(screen.getByLabelText(/phone number/i), { target: { value: '555-9999' } });
    fireEvent.click(screen.getByRole('button', { name: /search/i }));

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /release passes/i })).not.toBeInTheDocument();
      expect(screen.getByText(/no releasable passes found/i)).toBeInTheDocument();
    });
  });

  it('hides name/email fields when user is authenticated', async () => {
    vi.mocked(passesAPI.searchByPhone).mockResolvedValue([makePass()]);
    renderWinnerSearch();

    fireEvent.change(screen.getByLabelText(/phone number/i), { target: { value: '555-9999' } });
    fireEvent.click(screen.getByRole('button', { name: /search/i }));

    await waitFor(() => {
      expect(screen.queryByLabelText(/your name/i)).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/your email/i)).not.toBeInTheDocument();
    });
  });

  it('shows name/email fields when user is not authenticated', async () => {
    mockUseAuth.mockReturnValue({
      user: { email: null, role: 'dj', is_dj_network: true, is_station_office_network: true },
      loading: false,
      error: null,
      refetchUser: vi.fn(),
    });
    vi.mocked(passesAPI.searchByPhone).mockResolvedValue([makePass()]);
    renderWinnerSearch();

    fireEvent.change(screen.getByLabelText(/phone number/i), { target: { value: '555-9999' } });
    fireEvent.click(screen.getByRole('button', { name: /search/i }));

    await waitFor(() => {
      expect(screen.getByLabelText(/your name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/your email/i)).toBeInTheDocument();
    });
  });

  it('shows success message after a successful release', async () => {
    const releasedPass = makePass({ status: 'available', recipient_name: null, recipient_phone: null });
    vi.mocked(passesAPI.searchByPhone).mockResolvedValue([makePass()]);
    vi.mocked(passesAPI.releaseWinner).mockResolvedValue(releasedPass);
    renderWinnerSearch();

    fireEvent.change(screen.getByLabelText(/phone number/i), { target: { value: '555-9999' } });
    fireEvent.click(screen.getByRole('button', { name: /search/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /release passes/i })).toBeInTheDocument();
    });

    // Check the acknowledgment checkbox and fill in reason
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.change(screen.getByLabelText(/reason/i), {
      target: { value: 'Winner cannot attend.' },
    });
    fireEvent.click(screen.getByRole('button', { name: /release passes/i }));

    await waitFor(() => {
      expect(screen.getByText(/successfully released/i)).toBeInTheDocument();
    });
  });
});
