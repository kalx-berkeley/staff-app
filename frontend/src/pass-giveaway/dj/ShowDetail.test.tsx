import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { BrowserRouter, MemoryRouter } from 'react-router-dom';
import ShowDetail from './ShowDetail';
import { showsAPI, passesAPI } from '../api';
import { renderAndSettle } from '../../test/render';
import type { PassResponse, ShowResponse } from '../types';
import { recordPreviewGiveaway } from './previewGiveaways';

vi.mock('../api', () => ({
  showsAPI: { get: vi.fn(), getArtistInfo: vi.fn() },
  passesAPI: { getWinnerForEdit: vi.fn(), updateWinner: vi.fn() },
  venuePassesAPI: { checkWinner: vi.fn() },
}));

// The real DJ name input polls the on-air DJ; the page only needs its value.
vi.mock('../components', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../components')>()),
  DjNameInput: () => null,
}));

// A DJ studio computer by default; a test sets user to preview from home.
const auth = vi.hoisted(() => ({
  user: { email: null, role: 'dj', is_dj_network: true, is_station_office_network: true } as Record<string, unknown> | null,
}));
vi.mock('../../common/contexts/authHooks', () => ({ useAuth: () => ({ user: auth.user }) }));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useParams: () => ({ id: '1' }), useNavigate: () => vi.fn() };
});

const hoursAgo = (hours: number) => new Date(Date.now() - hours * 60 * 60 * 1000).toISOString();

const winner = (overrides: Partial<PassResponse> = {}) =>
  ({
    id: 5,
    show_id: 1,
    pass_type: 'pair',
    status: 'given_away',
    recipient_name: 'Jnae Winner',
    recipient_phone: '5105550100',
    recipient_email: null,
    given_away_by_dj: 'DJ Test',
    given_away_at: hoursAgo(1),
    ...overrides,
  }) as PassResponse;

const makeShow = (passes: PassResponse[], overrides: Partial<ShowResponse> = {}) =>
  ({
    id: 1,
    event_name: 'Test Band',
    genre: ['Rock'],
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
    passes,
    attempts: [],
    available_pair_count: 0,
    ...overrides,
  }) as unknown as ShowResponse;

const renderPage = async (show: ShowResponse, djName = 'DJ Test') => {
  localStorage.setItem('kalx_dj_name', djName);
  vi.mocked(showsAPI.get).mockResolvedValue(show);
  await renderAndSettle(
    <BrowserRouter>
      <ShowDetail />
    </BrowserRouter>
  );
  await screen.findAllByText(/Jnae Winner/);
  // A giveaway this shift puts a warning in front of the page
  const acknowledge = screen.queryByRole('button', { name: 'I understand, show me this show' });
  if (acknowledge) fireEvent.click(acknowledge);
  await screen.findByText('Venue:');
};

describe('DJ ShowDetail winner editing', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('never shows the staff instructions, which are for staff only', async () => {
    await renderPage(
      makeShow([winner()], {
        on_air_description: 'On-air text',
        staff_instructions: 'Staff-only pickup details',
      })
    );

    expect(screen.getByText('On-air text')).toBeInTheDocument();
    expect(screen.queryByText(/Staff-only pickup details/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Staff Instructions/)).not.toBeInTheDocument();
  });

  it('offers the DJ who gave the passes away an Edit button', async () => {
    await renderPage(makeShow([winner()]));

    expect(screen.getByRole('button', { name: 'Edit' })).toBeInTheDocument();
  });

  it('hides Edit from another DJ', async () => {
    await renderPage(makeShow([winner()]), 'DJ Other');

    expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument();
  });

  it('hides Edit after 4 hours', async () => {
    await renderPage(makeShow([winner({ given_away_at: hoursAgo(5) })]));

    expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument();
  });

  it('hides Edit for a closed show', async () => {
    await renderPage(makeShow([winner()], { status: 'closed' }));

    expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument();
  });

  it('shows the corrected winner after saving', async () => {
    vi.mocked(passesAPI.getWinnerForEdit).mockResolvedValue(winner());
    vi.mocked(passesAPI.updateWinner).mockResolvedValue(winner({ recipient_name: 'Jane Winner' }));
    await renderPage(makeShow([winner()]));

    fireEvent.click(screen.getByRole('button', { name: 'Edit' }));
    const name = await screen.findByDisplayValue('Jnae Winner');
    fireEvent.change(name, { target: { value: 'Jane Winner' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText('Jane Winner')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Save' })).not.toBeInTheDocument();
  });
});

describe('DJ ShowDetail right after a giveaway', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  const available = { id: 6, show_id: 1, pass_type: 'pair', status: 'available' } as PassResponse;

  const renderAt = async (state: unknown) => {
    localStorage.setItem('kalx_dj_name', 'DJ Test');
    vi.mocked(showsAPI.get).mockResolvedValue(makeShow([winner(), available], { available_pair_count: 1 }));
    await renderAndSettle(
      <MemoryRouter initialEntries={[{ pathname: '/dj/shows/1', state }]}>
        <ShowDetail />
      </MemoryRouter>
    );
    await screen.findAllByText('Jnae Winner');
  };

  it('thanks the DJ and hides the off-the-mic button just after giving away', async () => {
    await renderAt({ justGaveAway: true });
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Pass pair given away to Jnae Winner. Thanks!');
    expect(screen.queryByRole('button', { name: "I'm off the mic" })).not.toBeInTheDocument();
  });

  it('records the attempt without claiming a giveaway just after Tried', async () => {
    vi.mocked(showsAPI.get).mockResolvedValue(makeShow([available], { available_pair_count: 1 }));
    localStorage.setItem('kalx_dj_name', 'DJ Test');
    await renderAndSettle(
      <MemoryRouter initialEntries={[{ pathname: '/dj/shows/1', state: { justTried: true } }]}>
        <ShowDetail />
      </MemoryRouter>
    );
    const status = await screen.findByRole('status');
    expect(status).toHaveTextContent('Attempt recorded. No pass was given away');
    expect(status).not.toHaveTextContent('given away to');
    expect(screen.getByRole('button', { name: "I'm off the mic" })).toBeInTheDocument();
  });

  it('warns the DJ who comes back this shift that they can\'t give away passes, before showing the page', async () => {
    await renderAt(null);
    const gate = screen.getByRole('alert');
    expect(gate).toHaveTextContent("You can't give away passes to this show right now");
    expect(gate).toHaveTextContent('You already gave away a pass pair for Test Band to Jnae Winner');
    expect(gate).toHaveTextContent("Please don't announce these passes on air.");
    expect(screen.queryByText('Venue:')).not.toBeInTheDocument();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'I understand, show me this show' }));

    expect(await screen.findByText('Venue:')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: "I'm off the mic" })).not.toBeInTheDocument();
  });
});

describe('DJ ShowDetail preview away from the DJ studio', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
    auth.user = { email: 'promo@example.com', role: 'promotions', is_dj_network: false, is_station_office_network: false };
  });
  afterEach(() => {
    auth.user = { email: null, role: 'dj', is_dj_network: true, is_station_office_network: true };
  });

  const available = { id: 6, show_id: 1, pass_type: 'pair', status: 'available' } as PassResponse;

  const renderAt = async (state: unknown) => {
    localStorage.setItem('kalx_dj_name', 'DJ Test');
    vi.mocked(showsAPI.get).mockResolvedValue(makeShow([available], { available_pair_count: 1 }));
    await renderAndSettle(
      <MemoryRouter initialEntries={[{ pathname: '/dj/shows/1', state }]}>
        <ShowDetail />
      </MemoryRouter>
    );
  };

  it('thanks the DJ for a preview giveaway, says nothing was recorded, and hides the off-the-mic button', async () => {
    recordPreviewGiveaway({ show_id: 1, given_away_by_dj: 'DJ Test', recipient_name: 'Pat Caller' });
    await renderAt({ justGaveAway: true });

    const status = await screen.findByRole('status');
    expect(status).toHaveTextContent('Pass pair given away to Pat Caller. Thanks!');
    expect(status).toHaveTextContent('Preview only: nothing was recorded.');
    expect(screen.queryByRole('button', { name: "I'm off the mic" })).not.toBeInTheDocument();
  });

  it('warns before showing a show the DJ gave away in preview this shift', async () => {
    recordPreviewGiveaway({ show_id: 1, given_away_by_dj: 'DJ Test', recipient_name: 'Pat Caller' });
    await renderAt(null);

    expect(await screen.findByRole('alert')).toHaveTextContent("You can't give away passes to this show right now");
  });

  it('says a preview Tried recorded nothing', async () => {
    await renderAt({ justTried: true });

    expect(await screen.findByRole('status')).toHaveTextContent('Preview only: no attempt was recorded.');
    expect(screen.getByRole('button', { name: "I'm off the mic" })).toBeInTheDocument();
  });
});

describe('DJ ShowDetail with pairs pre-assigned to other DJs', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  const pair = (overrides: Partial<PassResponse>) =>
    ({ id: 6, show_id: 1, pass_type: 'pair', status: 'available', ...overrides }) as PassResponse;

  const renderWith = async (passes: PassResponse[]) => {
    localStorage.setItem('kalx_dj_name', 'DJ Test');
    vi.mocked(showsAPI.get).mockResolvedValue(
      makeShow(passes, { available_pair_count: passes.length }),
    );
    await renderAndSettle(
      <BrowserRouter>
        <ShowDetail />
      </BrowserRouter>
    );
  };

  it('covers the show details with a warning the DJ must click through', async () => {
    await renderWith([pair({ preassigned_dj: 'DJ Other', preassigned_date: '2099-12-30' })]);

    const gate = await screen.findByRole('alert');
    expect(gate).toHaveTextContent('These passes are pre-assigned to another DJ');
    expect(gate).toHaveTextContent('DJ Other for their show on Wednesday, December 30, 2099');
    expect(screen.queryByText('Venue:')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: "I'm off the mic" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'I understand, show me this show' }));

    expect(await screen.findByText('Venue:')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: "I'm off the mic" })).toBeInTheDocument();
  });

  it('skips the warning when the DJ has an unassigned pair to give away', async () => {
    await renderWith([pair({ preassigned_dj: 'DJ Other' }), pair({ id: 7, preassigned_dj: null })]);
    expect(await screen.findByText('Venue:')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it("skips the warning for the DJ's own pre-assigned pair, ignoring case", async () => {
    await renderWith([pair({ preassigned_dj: 'dj test' })]);
    expect(await screen.findByText('Venue:')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
