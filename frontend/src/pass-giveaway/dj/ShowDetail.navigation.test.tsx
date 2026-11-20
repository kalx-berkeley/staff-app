import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent, act } from '@testing-library/react';
import { MemoryRouter, Routes, Route, Link } from 'react-router-dom';
import ShowDetail from './ShowDetail';
import GiveawayPage from './GiveawayPage';
import { showsAPI } from '../api';
import { renderAndSettle } from '../../test/render';
import type { ShowResponse } from '../types';
import type { GiveawayOutcome } from './PassGiveawayForm';
import { persona, withOnAir } from './testOnAir';

// Separate from ShowDetail.test.tsx, which mocks useParams to one show and
// useNavigate: these tests move between real routes.

vi.mock('../api', () => ({
  showsAPI: { get: vi.fn(), getArtistInfo: vi.fn().mockResolvedValue(null) },
  passesAPI: {},
  venuePassesAPI: {},
}));
// The form has its own tests; here it only reports an outcome.
vi.mock('./PassGiveawayForm', () => ({
  default: ({ onSuccess }: { onSuccess: (outcome: GiveawayOutcome) => void }) => (
    <button onClick={() => onSuccess('given_away')}>Record winner</button>
  ),
}));
vi.mock('../../common/contexts/authHooks', () => ({
  useAuth: () => ({
    user: { email: null, role: 'dj', is_dj_network: true, is_station_office_network: true },
  }),
}));
vi.mock('../tracking', () => ({ useGiveawayVisit: () => null }));

const makeShow = (id: number, eventName: string) =>
  ({
    id,
    event_name: eventName,
    genre: [],
    bands: [],
    venue: { id: 2, name: 'The Venue', address: '1 Main St', has_logo: false },
    show_date: '2099-12-31',
    show_time: '20:00:00',
    show_start_date: null,
    age_restriction: 'all_ages',
    wheelchair_accessible: 'yes',
    guest_list_requirements: { requires_email_address: false },
    status: 'published',
    planned_close_date: null,
    planned_close_time: null,
    passes: [{ id: id * 10, show_id: id, pass_type: 'pair', status: 'available' }],
    attempts: [],
    available_pair_count: 1,
  }) as unknown as ShowResponse;

const ShowsList = () => (
  <div>
    <h2>Shows list</h2>
    <Link to="/dj/shows/1">Open show one</Link>
  </div>
);

/** The DJ routes, starting at *entries* (the last one is the current page). */
const renderRoutes = async (entries: string[]) => {
  await renderAndSettle(
    withOnAir(
      <MemoryRouter initialEntries={entries} initialIndex={entries.length - 1}>
        <Link to="/dj/shows/2">Go to show</Link>
        <Routes>
          <Route path="/dj/shows" element={<ShowsList />} />
          <Route path="/dj/shows/:id" element={<ShowDetail />} />
          <Route path="/dj/shows/:id/giveaway" element={<GiveawayPage />} />
          <Route path="/dj/my-passes" element={<h2>My passes</h2>} />
        </Routes>
      </MemoryRouter>,
      persona(1, 'DJ Test'),
    ),
  );
};

const click = async (element: HTMLElement) => {
  await act(async () => fireEvent.click(element));
};

describe('DJ ShowDetail navigation', () => {
  beforeEach(() => {
    vi.mocked(showsAPI.get).mockImplementation(async (id: number) =>
      makeShow(id, id === 1 ? 'Show One' : 'Show Two'),
    );
  });

  it('Back goes to the page the DJ came from', async () => {
    await renderRoutes(['/dj/my-passes', '/dj/shows/1']);
    await screen.findByRole('heading', { name: 'Show One' });

    await click(screen.getByRole('button', { name: '← Back' }));

    expect(await screen.findByRole('heading', { name: 'My passes' })).toBeInTheDocument();
  });

  it('Back goes to the shows list when the tab opened on the show', async () => {
    await renderRoutes(['/dj/shows/1']);
    await screen.findByRole('heading', { name: 'Show One' });

    await click(screen.getByRole('button', { name: '← Back' }));

    expect(await screen.findByRole('heading', { name: 'Shows list' })).toBeInTheDocument();
  });

  it('Back goes to the previous show after the spin-match toast opened another', async () => {
    await renderRoutes(['/dj/shows', '/dj/shows/1']);
    await screen.findByRole('heading', { name: 'Show One' });
    await click(screen.getByText('Go to show'));
    await screen.findByRole('heading', { name: 'Show Two' });

    await click(screen.getByRole('button', { name: '← Back' }));

    expect(await screen.findByRole('heading', { name: 'Show One' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Show Two' })).not.toBeInTheDocument();
  });

  it('after a giveaway, thanks the DJ and Back skips the giveaway form', async () => {
    await renderRoutes(['/dj/my-passes', '/dj/shows/1']);
    await click(await screen.findByRole('button', { name: "I'm off the mic" }));
    await click(await screen.findByRole('button', { name: 'Record winner' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Pass pair given away');
    expect(screen.queryByRole('button', { name: "I'm off the mic" })).not.toBeInTheDocument();

    await click(screen.getByRole('button', { name: '← Back' }));

    expect(await screen.findByRole('heading', { name: 'My passes' })).toBeInTheDocument();
  });

  it('opens the next show fresh, not with the last show\'s just-gave-away state', async () => {
    await renderRoutes(['/dj/shows', '/dj/shows/1']);
    await click(await screen.findByRole('button', { name: "I'm off the mic" }));
    await click(await screen.findByRole('button', { name: 'Record winner' }));
    await screen.findByRole('status');

    await click(screen.getByText('Go to show'));

    await screen.findByRole('heading', { name: 'Show Two' });
    expect(await screen.findByRole('button', { name: "I'm off the mic" })).toBeInTheDocument();
  });
});
