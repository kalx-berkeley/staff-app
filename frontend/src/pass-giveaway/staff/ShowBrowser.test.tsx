import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { renderAndSettle } from '../../test/render';
import ShowBrowser from './ShowBrowser';
import { showsAPI } from '../api';
import type { ShowSummary } from '../types';

vi.mock('../api', () => ({
  showsAPI: { list: vi.fn() },
  venuesAPI: { list: vi.fn().mockResolvedValue([]) },
}));

const show = (overrides: Partial<ShowSummary>): ShowSummary => ({
  id: 1,
  event_name: 'Rock Concert',
  genre: ['Rock'],
  venue: { id: 1, name: 'The Venue', venue_type: 'music' },
  show_date: '2030-12-31',
  show_time: '20:00',
  show_start_date: null,
  caller_special_instructions: null,
  age_restriction: '21+',
  movie_rating: null,
  wheelchair_accessible: 'yes',
  num_pass_pairs: 3,
  staff_pass_adjustment: 0,
  num_staff_passes: 3,
  num_tabler_passes: 0,
  status: 'published',
  available_pair_count: 3,
  available_staff_count: 3,
  guest_hold_staff_count: 0,
  unassigned_pair_count: 3,
  clothespin_available: true,
  planned_close_passed: false,
  co_announce: false,
  published_at: null,
  bands: [],
  is_mine: false,
  in_feature_bin: false,
  feature_bin_releases: [],
  on_kalx_live: false,
  kalx_live_appearances: [],
  ...overrides,
});

const shows: ShowSummary[] = [
  show({ id: 1, event_name: 'Has Passes' }),
  show({ id: 2, event_name: 'All Claimed', available_staff_count: 0 }),
  // Its only staff pass is held for another staff member's +1 guest, which a claim takes over.
  show({ id: 3, event_name: 'Guest Hold Only', available_staff_count: 0, guest_hold_staff_count: 1 }),
  show({ id: 4, event_name: 'Past Planned Close', planned_close_passed: true }),
  show({ id: 5, event_name: 'Closed Show', status: 'closed' }),
];

const renderBrowser = async () => {
  await renderAndSettle(
    <BrowserRouter>
      <ShowBrowser />
    </BrowserRouter>
  );
  await screen.findByText('Has Passes');
};

const chooseFilter = (value: string) =>
  fireEvent.change(screen.getByRole('combobox', { name: 'Filter by status' }), { target: { value } });

describe('Staff ShowBrowser status filter', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    vi.mocked(showsAPI.list).mockResolvedValue(shows);
  });

  it('shows every published show by default', async () => {
    await renderBrowser();

    expect(screen.getByRole('combobox', { name: 'Filter by status' })).toHaveValue('published');
    expect(screen.getByText('All Claimed')).toBeInTheDocument();
    expect(screen.getByText('Past Planned Close')).toBeInTheDocument();
    expect(screen.queryByText('Closed Show')).not.toBeInTheDocument();
  });

  it('shows only shows with staff passes left to claim', async () => {
    await renderBrowser();

    chooseFilter('available');

    expect(await screen.findByText('Guest Hold Only')).toBeInTheDocument();
    expect(screen.getByText('Has Passes')).toBeInTheDocument();
    expect(screen.queryByText('All Claimed')).not.toBeInTheDocument();
    expect(screen.queryByText('Past Planned Close')).not.toBeInTheDocument();
    expect(screen.queryByText('Closed Show')).not.toBeInTheDocument();
  });

  it('says so when no show has staff passes available', async () => {
    vi.mocked(showsAPI.list).mockResolvedValue([shows[0], shows[1]].map((s) => ({ ...s, available_staff_count: 0 })));
    await renderAndSettle(
      <BrowserRouter>
        <ShowBrowser />
      </BrowserRouter>
    );
    await screen.findByText('All Claimed');

    chooseFilter('available');

    expect(await screen.findByText('No shows have staff passes available at this time.')).toBeInTheDocument();
  });
});
