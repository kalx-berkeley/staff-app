import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import GiveawayPage from './GiveawayPage';
import { showsAPI } from '../api';
import { renderAndSettle } from '../../test/render';
import type { PassResponse, ShowResponse } from '../types';
import { clearGiveawayOutcome, peekGiveawayOutcome, peekGiveawayVisitId } from './giveawayOutcome';

vi.mock('../api', () => ({
  showsAPI: { get: vi.fn(), getArtistInfo: vi.fn() },
}));

// The form and DJ name input have their own tests; this page only places them.
vi.mock('./PassGiveawayForm', () => ({
  default: ({ pass, viewOnly }: { pass: PassResponse; viewOnly?: boolean }) => (
    <div>Giveaway form for pass {pass.id}{viewOnly && ' (view only)'}</div>
  ),
}));
// A DJ studio computer by default; a test sets user to view from home.
const auth = vi.hoisted(() => ({
  user: { email: null, role: 'dj', is_dj_network: true, is_station_office_network: true } as Record<string, unknown> | null,
}));
vi.mock('../../common/contexts/authHooks', () => ({ useAuth: () => ({ user: auth.user }) }));
vi.mock('../tracking', () => ({ useGiveawayVisit: () => 'visit-1' }));

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

const makeShow = (passes: PassResponse[], overrides: Partial<ShowResponse> = {}) =>
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
    ...overrides,
  }) as unknown as ShowResponse;

const renderPage = async (show: ShowResponse) => {
  vi.mocked(showsAPI.get).mockResolvedValue(show);
  await renderAndSettle(
    <BrowserRouter>
      <GiveawayPage />
    </BrowserRouter>
  );
};

const DJ_STUDIO_USER = { email: null, role: 'dj', is_dj_network: true, is_station_office_network: true };

describe('DJ GiveawayPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    auth.user = DJ_STUDIO_USER;
    clearGiveawayOutcome();
  });

  it('tells the show page the DJ opened the form, so it can ask about Tried', async () => {
    await renderPage(makeShow([pass(1)]));

    expect(await screen.findByText('Giveaway form for pass 1')).toBeInTheDocument();
    expect(peekGiveawayOutcome('1')).toBe('opened');
    expect(peekGiveawayVisitId('1')).toBe('visit-1');
  });

  it("doesn't tell the show page anything when Tried can't be used", async () => {
    await renderPage(makeShow([pass(1)], { status: 'closed' }));
    await screen.findByRole('alert');

    expect(peekGiveawayOutcome('1')).toBeNull();
  });

  it('lets a DJ studio computer give passes away', async () => {
    await renderPage(makeShow([pass(1)]));

    expect(await screen.findByText('Giveaway form for pass 1')).toBeInTheDocument();
    expect(screen.queryByText(/view only/i)).not.toBeInTheDocument();
  });

  it('is view only for promotions staff away from the DJ studio', async () => {
    auth.user = { email: 'promo@example.com', role: 'promotions', is_dj_network: false, is_station_office_network: false };
    await renderPage(makeShow([pass(1)]));

    expect(await screen.findByText('Giveaway form for pass 1 (view only)')).toBeInTheDocument();
    expect(screen.getByRole('note')).toHaveTextContent('Giveaways can only be recorded from the DJ studio');
    expect(peekGiveawayOutcome('1')).toBeNull();
  });

  it('records for real while impersonating the DJ studio network in staging', async () => {
    auth.user = {
      email: null,
      role: 'dj',
      is_dj_network: true,
      is_station_office_network: true,
      is_staging: true,
      is_impersonating_dj_network: true,
    };
    await renderPage(makeShow([pass(1)]));

    expect(await screen.findByText('Giveaway form for pass 1')).toBeInTheDocument();
    expect(screen.queryByRole('note')).not.toBeInTheDocument();
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

  it('has no winner form or Tried for a closed show, only the notice', async () => {
    await renderPage(makeShow([pass(1)], { status: 'closed' }));

    const notice = await screen.findByRole('alert');
    expect(notice).toHaveTextContent("Don't announce this show on air");
    expect(notice).toHaveTextContent('The pass giveaway for Test Band has closed.');
    expect(screen.queryByText(/Giveaway form for pass/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '← Back to Show' })).toBeInTheDocument();
  });

  it('has no winner form once the planned close time has passed', async () => {
    await renderPage(makeShow([pass(1)], { planned_close_passed: true }));

    expect(await screen.findByRole('alert')).toHaveTextContent("Don't announce this show on air");
    expect(screen.queryByText(/Giveaway form for pass/)).not.toBeInTheDocument();
  });

  it('takes the form away when the show closes while the page is open', async () => {
    await renderPage(makeShow([pass(1)]));
    expect(await screen.findByText('Giveaway form for pass 1')).toBeInTheDocument();

    vi.mocked(showsAPI.get).mockResolvedValue(makeShow([pass(1)], { status: 'closed' }));
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'));
    });

    expect(await screen.findByRole('alert')).toHaveTextContent("Don't announce this show on air");
    expect(screen.queryByText(/Giveaway form for pass/)).not.toBeInTheDocument();
  });
});
