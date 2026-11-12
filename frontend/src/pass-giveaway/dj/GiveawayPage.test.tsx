import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import GiveawayPage from './GiveawayPage';
import { showsAPI } from '../api';
import { renderAndSettle } from '../../test/render';
import type { PassResponse, ShowResponse } from '../types';

vi.mock('../api', () => ({
  showsAPI: { get: vi.fn(), getArtistInfo: vi.fn() },
}));

// The form and DJ name input have their own tests; this page only places them.
vi.mock('./PassGiveawayForm', () => ({
  default: ({ pass }: { pass: PassResponse }) => <div>Giveaway form for pass {pass.id}</div>,
}));
vi.mock('../components', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../components')>()),
  DjNameInput: () => null,
}));
// A DJ studio computer by default; a test sets user to preview from home.
const auth = vi.hoisted(() => ({
  user: { email: null, role: 'dj', is_dj_network: true, is_station_office_network: true } as Record<string, unknown> | null,
}));
vi.mock('../../common/contexts/authHooks', () => ({ useAuth: () => ({ user: auth.user }) }));
vi.mock('../tracking', () => ({ useGiveawayVisit: () => null }));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useParams: () => ({ id: '1' }), useNavigate: () => vi.fn() };
});

const pass = (id: number, overrides: Partial<PassResponse> = {}) =>
  ({
    id,
    show_id: 1,
    pass_type: 'pair',
    status: 'available',
    preassigned_dj: null,
    preassigned_date: null,
    ...overrides,
  }) as PassResponse;

const makeShow = (passes: PassResponse[]) =>
  ({
    id: 1,
    event_name: 'Test Band',
    genre: ['Rock'],
    bands: [],
    venue: { id: 2, name: 'The Venue', address: '1 Main St', has_logo: false, win_frequency_days: 30 },
    show_date: '2099-12-31',
    show_time: '20:00:00',
    show_start_date: null,
    age_restriction: 'all_ages',
    wheelchair_accessible: 'yes',
    guest_list_requirements: { requires_email_address: false },
    status: 'published',
    passes,
    attempts: [],
    available_pair_count: passes.filter((p) => p.status === 'available').length,
  }) as unknown as ShowResponse;

const renderPage = async (show: ShowResponse) => {
  vi.mocked(showsAPI.get).mockResolvedValue(show);
  await renderAndSettle(
    <BrowserRouter>
      <GiveawayPage />
    </BrowserRouter>
  );
};

describe('DJ GiveawayPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('shows one giveaway form and counts the remaining pass pairs', async () => {
    await renderPage(makeShow([pass(1), pass(2), pass(3)]));

    expect(await screen.findByText('Giveaway form for pass 1')).toBeInTheDocument();
    expect(screen.queryByText(/Giveaway form for pass [23]/)).not.toBeInTheDocument();
    expect(screen.getByText('2 more pass pairs available after this one.')).toBeInTheDocument();
    expect(screen.queryByText(/given away in order|Waiting for the first/)).not.toBeInTheDocument();
  });

  it('says "1 more pass pair" and lists pre-assignments among the rest', async () => {
    await renderPage(makeShow([pass(1), pass(2, { preassigned_dj: 'DJ Other', preassigned_date: '2099-12-30' })]));

    expect(await screen.findByText('1 more pass pair available after this one.')).toBeInTheDocument();
    expect(screen.getByText('DJ Other')).toBeInTheDocument();
  });

  it('shows no remaining count when only one pass pair is left', async () => {
    await renderPage(makeShow([pass(1), pass(2, { status: 'given_away' })]));

    expect(await screen.findByText('Giveaway form for pass 1')).toBeInTheDocument();
    expect(screen.queryByText(/more pass pair/)).not.toBeInTheDocument();
  });
});
