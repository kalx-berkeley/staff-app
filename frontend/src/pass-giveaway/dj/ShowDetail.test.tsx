import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, screen, fireEvent } from '@testing-library/react';
import { BrowserRouter, MemoryRouter } from 'react-router-dom';
import ShowDetail from './ShowDetail';
import { showsAPI, passesAPI } from '../api';
import { renderAndSettle } from '../../test/render';
import type { OnAirIdentity, PassResponse, ShowResponse } from '../types';
import { persona, withOnAir } from './testOnAir';
import { clearGiveawayOutcome, markGiveawayOpened, setGiveawayOutcome } from './giveawayOutcome';
import type { GiveawayOutcome } from './PassGiveawayForm';

const DJ_TEST = persona(1, 'DJ Test');

vi.mock('../api', () => ({
  showsAPI: { get: vi.fn(), getArtistInfo: vi.fn(), recordAttempt: vi.fn() },
  passesAPI: { getWinnerForEdit: vi.fn(), updateWinner: vi.fn() },
  venuePassesAPI: { checkWinner: vi.fn() },
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
    given_away_persona_id: 1,
    given_away_specialty_show_id: null,
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

const renderPage = async (show: ShowResponse, identity: OnAirIdentity | null = DJ_TEST) => {
  vi.mocked(showsAPI.get).mockResolvedValue(show);
  await renderAndSettle(
    withOnAir(
      <BrowserRouter>
        <ShowDetail />
      </BrowserRouter>,
      identity,
    ),
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

  it('gives the DJ the KALX phone number to announce', async () => {
    await renderPage(makeShow([winner()]));

    expect(screen.getByText('(510) 642-5259')).toBeInTheDocument();
    expect(screen.getByText('(510) 642-KALX')).toBeInTheDocument();
  });

  it('offers the DJ who gave the passes away an Edit button', async () => {
    await renderPage(makeShow([winner()]));

    expect(screen.getByRole('button', { name: 'Edit' })).toBeInTheDocument();
  });

  it('hides Edit from another DJ', async () => {
    await renderPage(makeShow([winner()]), persona(2, 'DJ Other'));

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

  const renderAt = async (outcome: GiveawayOutcome | null) => {
    if (outcome) setGiveawayOutcome('1', outcome);
    vi.mocked(showsAPI.get).mockResolvedValue(makeShow([winner(), available], { available_pair_count: 1 }));
    await renderAndSettle(
      withOnAir(
        <MemoryRouter initialEntries={['/dj/shows/1']}>
          <ShowDetail />
        </MemoryRouter>,
        DJ_TEST,
      ),
    );
    await screen.findAllByText('Jnae Winner');
  };

  it('thanks the DJ and hides the off-the-mic button just after giving away', async () => {
    await renderAt('given_away');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Pass pair given away to Jnae Winner. Thanks!');
    expect(screen.queryByRole('button', { name: "I'm off the mic" })).not.toBeInTheDocument();
  });

  it('records the attempt without claiming a giveaway just after Tried', async () => {
    setGiveawayOutcome('1', 'tried');
    vi.mocked(showsAPI.get).mockResolvedValue(makeShow([available], { available_pair_count: 1 }));
    await renderAndSettle(
      withOnAir(
        <MemoryRouter initialEntries={['/dj/shows/1']}>
          <ShowDetail />
        </MemoryRouter>,
        DJ_TEST,
      ),
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

describe('DJ ShowDetail after leaving the giveaway page without recording anything', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    clearGiveawayOutcome();
  });

  const available = { id: 6, show_id: 1, pass_type: 'pair', status: 'available' } as PassResponse;

  const renderBack = async (show: ShowResponse) => {
    markGiveawayOpened('1', 'visit-1');
    vi.mocked(showsAPI.get).mockResolvedValue(show);
    await renderAndSettle(
      withOnAir(
        <MemoryRouter initialEntries={['/dj/shows/1']}>
          <ShowDetail />
        </MemoryRouter>,
        DJ_TEST,
      ),
    );
    await screen.findByText('Venue:');
  };

  it('asks whether nobody called in, and records Tried for the giveaway page visit', async () => {
    vi.mocked(showsAPI.recordAttempt).mockResolvedValue({
      id: 9,
      dj_name: 'DJ Test',
      attempted_at: hoursAgo(0),
    });
    await renderBack(makeShow([available], { available_pair_count: 1 }));

    expect(screen.getByRole('region', { name: 'Did nobody call in?' })).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole('button', { name: 'I announced them, nobody called: record Tried' }),
    );

    expect(await screen.findByRole('status')).toHaveTextContent('Attempt recorded.');
    expect(showsAPI.recordAttempt).toHaveBeenCalledWith(1, 'visit-1');
    expect(screen.queryByRole('region', { name: 'Did nobody call in?' })).not.toBeInTheDocument();
    expect(screen.getByText('Previous Giveaway Activity')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: "I'm off the mic" })).toBeInTheDocument();
  });

  it('records nothing when the DJ says they didn\'t announce the passes', async () => {
    await renderBack(makeShow([available], { available_pair_count: 1 }));

    fireEvent.click(screen.getByRole('button', { name: "I didn't announce them" }));

    expect(screen.queryByRole('region', { name: 'Did nobody call in?' })).not.toBeInTheDocument();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(showsAPI.recordAttempt).not.toHaveBeenCalled();
  });

  it('keeps asking and shows the error when recording Tried fails', async () => {
    vi.mocked(showsAPI.recordAttempt).mockRejectedValue({
      detail: 'Cannot record attempts for closed shows',
    });
    await renderBack(makeShow([available], { available_pair_count: 1 }));

    fireEvent.click(
      screen.getByRole('button', { name: 'I announced them, nobody called: record Tried' }),
    );

    expect(await screen.findByText('Cannot record attempts for closed shows')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Did nobody call in?' })).toBeInTheDocument();
  });

  it("doesn't ask once the giveaway has closed", async () => {
    await renderBack(makeShow([available], { available_pair_count: 1, status: 'closed' }));

    expect(screen.queryByRole('region', { name: 'Did nobody call in?' })).not.toBeInTheDocument();
  });

  it("doesn't ask after Tried or Give Away on the giveaway page", async () => {
    markGiveawayOpened('1', 'visit-1');
    setGiveawayOutcome('1', 'tried');
    vi.mocked(showsAPI.get).mockResolvedValue(makeShow([available], { available_pair_count: 1 }));
    await renderAndSettle(
      withOnAir(
        <MemoryRouter initialEntries={['/dj/shows/1']}>
          <ShowDetail />
        </MemoryRouter>,
        DJ_TEST,
      ),
    );

    expect(await screen.findByRole('status')).toHaveTextContent('Attempt recorded.');
    expect(screen.queryByRole('region', { name: 'Did nobody call in?' })).not.toBeInTheDocument();
  });

  it("doesn't ask on another show's page", async () => {
    markGiveawayOpened('2', 'visit-2');
    vi.mocked(showsAPI.get).mockResolvedValue(makeShow([available], { available_pair_count: 1 }));
    await renderAndSettle(
      withOnAir(
        <MemoryRouter initialEntries={['/dj/shows/1']}>
          <ShowDetail />
        </MemoryRouter>,
        DJ_TEST,
      ),
    );
    await screen.findByText('Venue:');

    expect(screen.queryByRole('region', { name: 'Did nobody call in?' })).not.toBeInTheDocument();
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
    vi.mocked(showsAPI.get).mockResolvedValue(
      makeShow(passes, { available_pair_count: passes.length }),
    );
    await renderAndSettle(
      withOnAir(
        <BrowserRouter>
          <ShowDetail />
        </BrowserRouter>,
        DJ_TEST,
      ),
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

  it("skips the warning for the on-air DJ's own pre-assigned pair", async () => {
    await renderWith([pair({ preassigned_dj: 'DJ Test', preassigned_persona_id: 1, preassigned_specialty_show_id: null })]);
    expect(await screen.findByText('Venue:')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});

describe('DJ ShowDetail for a show whose giveaway has closed', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  const available = { id: 6, show_id: 1, pass_type: 'pair', status: 'available' } as PassResponse;

  const renderShow = async (overrides: Partial<ShowResponse>) => {
    vi.mocked(showsAPI.get).mockResolvedValue(
      makeShow([available], { available_pair_count: 1, ...overrides }),
    );
    await renderAndSettle(
      withOnAir(
        <BrowserRouter>
          <ShowDetail />
        </BrowserRouter>,
        DJ_TEST,
      ),
    );
  };

  it('tells the DJ not to announce a closed show, with no off-the-mic button', async () => {
    await renderShow({ status: 'closed' });

    const notice = await screen.findByRole('alert');
    expect(notice).toHaveTextContent("Don't announce this show on air");
    expect(notice).toHaveTextContent('The pass giveaway for Test Band has closed.');
    expect(screen.getByRole('button', { name: '← Pick a different show' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: "I'm off the mic" })).not.toBeInTheDocument();
    // Nor the on-air instructions, which read as if the passes can be announced
    expect(screen.queryByText(/to win\./)).not.toBeInTheDocument();
    // The show details are still there to look at
    expect(screen.getByText('Venue:')).toBeInTheDocument();
    // Unawarded pairs are still "available" in the data, but not to give away
    expect(screen.getByText(/Pass Pairs — giveaway closed/)).toBeInTheDocument();
    expect(screen.queryByText(/1 of 1 available/)).not.toBeInTheDocument();
  });

  it('says when the planned close time passed for a show not yet closed', async () => {
    await renderShow({
      planned_close_passed: true,
      planned_close_date: '2026-11-21',
      planned_close_time: '19:00:00',
    });

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The pass giveaway for Test Band closed at 7:00 PM on Saturday, November 21.',
    );
    expect(screen.queryByRole('button', { name: "I'm off the mic" })).not.toBeInTheDocument();
  });

  it('shows the closed notice instead of the pre-assigned warning', async () => {
    vi.mocked(showsAPI.get).mockResolvedValue(
      makeShow([{ ...available, preassigned_dj: 'DJ Other' }], {
        available_pair_count: 1,
        status: 'closed',
      }),
    );
    await renderAndSettle(
      withOnAir(
        <BrowserRouter>
          <ShowDetail />
        </BrowserRouter>,
        DJ_TEST,
      ),
    );

    const notice = await screen.findByRole('alert');
    expect(notice).toHaveTextContent("Don't announce this show on air");
    expect(screen.queryByText(/pre-assigned to another DJ/)).not.toBeInTheDocument();
  });

  it('notices the show closed when the DJ comes back to a tab left open', async () => {
    await renderShow({});
    expect(await screen.findByRole('button', { name: "I'm off the mic" })).toBeInTheDocument();

    vi.mocked(showsAPI.get).mockResolvedValue(
      makeShow([available], { available_pair_count: 1, status: 'closed' }),
    );
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'));
    });

    expect(await screen.findByRole('alert')).toHaveTextContent("Don't announce this show on air");
    expect(screen.queryByRole('button', { name: "I'm off the mic" })).not.toBeInTheDocument();
  });
});
