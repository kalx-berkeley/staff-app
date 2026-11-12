import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { BrowserRouter, MemoryRouter, Route, Routes, useNavigate } from 'react-router-dom';
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
    // The filters live in the URL, which BrowserRouter shares between tests.
    window.history.replaceState(null, '', '/');
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

  it("hides shows with no staff passes (such as a split show's on-air show)", async () => {
    vi.mocked(showsAPI.list).mockResolvedValue([
      ...shows,
      show({ id: 6, event_name: 'Pairs Only', num_staff_passes: 0, available_staff_count: 0 }),
    ]);
    await renderBrowser();

    expect(screen.queryByText('Pairs Only')).not.toBeInTheDocument();
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

describe('Staff ShowBrowser filters in the URL', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    vi.mocked(showsAPI.list).mockResolvedValue(shows);
  });

  it('keeps every filter after opening a show and going back', async () => {
    const ShowPage = () => {
      const navigate = useNavigate();
      return <button onClick={() => navigate(-1)}>Back</button>;
    };
    await renderAndSettle(
      <MemoryRouter initialEntries={['/staff/shows']}>
        <Routes>
          <Route path="/staff/shows" element={<ShowBrowser />} />
          <Route path="/staff/shows/:id" element={<ShowPage />} />
        </Routes>
      </MemoryRouter>
    );
    await screen.findByText('Has Passes');

    chooseFilter('all');
    fireEvent.change(screen.getByLabelText('Sort by:'), { target: { value: 'venue' } });
    fireEvent.change(screen.getByLabelText('Search'), { target: { value: 'Closed' } });
    fireEvent.change(screen.getByLabelText('Genre'), { target: { value: 'Rock' } });
    fireEvent.change(screen.getByLabelText('To:'), { target: { value: '12/31/2031' } });
    expect(await screen.findByText('Closed Show')).toBeInTheDocument();
    expect(screen.queryByText('Has Passes')).not.toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('link', { name: 'View' })[0]);
    fireEvent.click(await screen.findByRole('button', { name: 'Back' }));

    expect(await screen.findByText('Closed Show')).toBeInTheDocument();
    expect(screen.queryByText('Has Passes')).not.toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'Filter by status' })).toHaveValue('all');
    expect(screen.getByLabelText('Sort by:')).toHaveValue('venue');
    expect(screen.getByLabelText('Search')).toHaveValue('Closed');
    expect(screen.getByLabelText('Genre')).toHaveValue('Rock');
    expect(screen.getByLabelText('To:')).toHaveValue('12/31/2031');
  });
});
