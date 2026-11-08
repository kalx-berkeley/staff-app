import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import ShowDetail from './ShowDetail';
import { showsAPI, passesAPI } from '../api';
import { renderAndSettle } from '../../test/render';
import type { PassResponse, ShowResponse } from '../types';

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
  await screen.findByText('Jnae Winner');
};

describe('DJ ShowDetail winner editing', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
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
