import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import LegacyImport from './LegacyImport';
import { legacyImportAPI, passesAPI, showsAPI, venuesAPI } from '../api';
import { renderAndSettle } from '../../test/render';
import type { PassResponse, ShowSummary, VenueResponse } from '../types';

vi.mock('../api', () => ({
  legacyImportAPI: {
    checkEnabled: vi.fn(),
    listStaff: vi.fn(),
    importShow: vi.fn(),
    mergeShow: vi.fn(),
  },
  passesAPI: {
    getForShow: vi.fn(),
    releaseClaim: vi.fn(),
    releaseWinner: vi.fn(),
  },
  venuesAPI: {
    list: vi.fn(),
  },
  showsAPI: {
    listGenres: vi.fn().mockResolvedValue([]),
    suggestGenre: vi.fn().mockResolvedValue(null),
    list: vi.fn().mockResolvedValue([]),
    analyzeDescription: vi.fn(),
  },
  autocompleteAPI: {
    getDJNames: vi.fn().mockResolvedValue([]),
  },
  specialtyShowsAPI: {
    list: vi.fn().mockResolvedValue([]),
  },
}));

const makeVenue = (overrides: Partial<VenueResponse> = {}): VenueResponse => ({
  id: 1,
  name: 'Music Hall',
  address: '1 Main St',
  show_sourcing_instructions: null,
  pass_call_instructions: null,
  win_frequency_days: null,
  venue_type: 'music',
  default_wheelchair_accessible: null,
  default_age_restriction: null,
  default_movie_rating: null,
  default_num_pass_pairs: null,
  requires_phone_number: false,
  email_address_requirement: 'none',
  requires_email_address: false,
  staff_guest_requires_name: false, hold_close_notifications: false,
  default_lottery_enabled: false,
  default_lottery_window_hours: 24,
  default_dj_preassign_prohibition_days: null,
  default_close_hours_before_show: null,
  default_on_air_description: null,
  default_caller_special_instructions: null,
  has_logo: false,
  show_name_with_logo: false,
  deleted: false,
  promoter_id: null,
  promoter: null,
  shows_have_external_promoter: false,
  owner_emails: [],
  owner_details: [],
  contacts: [],
  ...overrides,
});

const musicHall = makeVenue();
const cinema = makeVenue({
  id: 2,
  name: 'Cinema',
  venue_type: 'movie_theater',
  default_movie_rating: 'PG-13',
});

const renderLegacyImport = () =>
  renderAndSettle(
    <MemoryRouter>
      <LegacyImport />
    </MemoryRouter>
  );

describe('LegacyImport movie rating', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(legacyImportAPI.checkEnabled).mockResolvedValue(true);
    vi.mocked(legacyImportAPI.listStaff).mockResolvedValue([]);
    vi.mocked(venuesAPI.list).mockResolvedValue([musicHall, cinema]);
  });

  it('replaces Age Restriction at a movie theater and takes its default', async () => {
    await renderLegacyImport();
    expect(screen.getByLabelText(/age restriction/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/movie rating/i)).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/^venue/i), { target: { value: '2' } });
    expect(await screen.findByLabelText(/movie rating/i)).toHaveValue('PG-13');
    expect(screen.queryByLabelText(/age restriction/i)).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/^venue/i), { target: { value: '1' } });
    expect(await screen.findByLabelText(/age restriction/i)).toBeInTheDocument();
  });

  it('sends the movie rating and no age restriction', async () => {
    vi.mocked(legacyImportAPI.importShow).mockResolvedValue({
      show_id: 7,
      on_air_winners_created: 0,
      staff_passes_claimed: 0,
      alternates_added: 0,
    });
    await renderLegacyImport();

    fireEvent.change(screen.getByLabelText(/^venue/i), { target: { value: '2' } });
    fireEvent.change(screen.getByLabelText(/event name/i), { target: { value: 'Old Movie' } });
    fireEvent.change(screen.getByLabelText(/show date/i), { target: { value: '2024-12-31' } });
    fireEvent.change(screen.getByLabelText(/show time/i), { target: { value: '20:00' } });
    fireEvent.change(await screen.findByLabelText(/movie rating/i), { target: { value: 'R' } });

    fireEvent.click(screen.getByRole('button', { name: /import show/i }));

    expect(await screen.findByText(/imported show #7/i)).toBeInTheDocument();
    expect(legacyImportAPI.importShow).toHaveBeenCalledWith(
      expect.objectContaining({ venue_id: 2, movie_rating: 'R', age_restriction: null })
    );
  });
});

describe('LegacyImport alternates', () => {
  const staff = [
    { id: 1, name: 'Ann Claimant', email: 'ann@test.com' },
    { id: 2, name: 'Bo Alternate', email: 'bo@test.com' },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(legacyImportAPI.checkEnabled).mockResolvedValue(true);
    vi.mocked(legacyImportAPI.listStaff).mockResolvedValue(staff);
    vi.mocked(venuesAPI.list).mockResolvedValue([musicHall]);
  });

  const fillShowFields = () => {
    fireEvent.change(screen.getByLabelText(/event name/i), { target: { value: 'Paper Show' } });
    fireEvent.change(screen.getByLabelText(/show date/i), { target: { value: '2099-12-31' } });
    fireEvent.change(screen.getByLabelText(/show time/i), { target: { value: '20:00' } });
  };

  const addRow = (button: RegExp, labelIndex: number, text: string) => {
    fireEvent.click(screen.getByRole('button', { name: button }));
    fireEvent.change(screen.getAllByLabelText(/staff member/i)[labelIndex], {
      target: { value: text },
    });
  };

  it('sends alternates once staff hold every staff pass', async () => {
    vi.mocked(legacyImportAPI.importShow).mockResolvedValue({
      show_id: 7,
      on_air_winners_created: 0,
      staff_passes_claimed: 1,
      alternates_added: 1,
    });
    await renderLegacyImport();
    fillShowFields();
    addRow(/add staff claimant/i, 0, 'ann@test.com');
    addRow(/add alternate/i, 1, 'bo@test.com');

    fireEvent.click(screen.getByRole('button', { name: /import show/i }));

    expect(await screen.findByText(/1 alternate\(s\)/i)).toBeInTheDocument();
    expect(legacyImportAPI.importShow).toHaveBeenCalledWith(
      expect.objectContaining({
        staff_passes: [{ staff_id: 1, has_guest: false, guest_name: null }],
        alternates: [{ staff_id: 2, has_guest: false, guest_name: null }],
      })
    );
    expect(screen.queryByLabelText(/staff member/i)).not.toBeInTheDocument();
  });

  it('blocks alternates while a staff pass is left over', async () => {
    await renderLegacyImport();
    fillShowFields();
    addRow(/add alternate/i, 0, 'bo@test.com');

    fireEvent.click(screen.getByRole('button', { name: /import show/i }));

    expect(await screen.findByText(/alternates can only be added/i)).toBeInTheDocument();
    expect(legacyImportAPI.importShow).not.toHaveBeenCalled();
  });

  it('blocks an alternate who also has a staff pass', async () => {
    await renderLegacyImport();
    fillShowFields();
    addRow(/add staff claimant/i, 0, 'ann@test.com');
    addRow(/add alternate/i, 1, 'ann@test.com');

    fireEvent.click(screen.getByRole('button', { name: /import show/i }));

    expect(await screen.findByText(/already has a staff pass/i)).toBeInTheDocument();
    expect(legacyImportAPI.importShow).not.toHaveBeenCalled();
  });
});

describe('LegacyImport releasing from an existing show', () => {
  const makePass = (overrides: Partial<PassResponse>): PassResponse =>
    ({
      id: 1,
      show_id: 5,
      pass_type: 'staff',
      status: 'available',
      recipient_name: null,
      recipient_phone: null,
      recipient_email: null,
      given_away_by_dj: null,
      staff_name: null,
      has_guest: false,
      guest_name: null,
      guest_of_pass_id: null,
      ...overrides,
    }) as PassResponse;

  const winner = makePass({
    id: 1,
    pass_type: 'pair',
    status: 'given_away',
    recipient_name: 'Cal Caller',
    recipient_phone: '5105551234',
    given_away_by_dj: 'DJ Test',
  });
  const openPair = makePass({ id: 2, pass_type: 'pair' });
  const claim = makePass({
    id: 3,
    status: 'claimed',
    staff_name: 'Ann Claimant',
    has_guest: true,
    guest_name: 'Pat',
  });
  const guestHold = makePass({
    id: 4,
    status: 'claimed',
    staff_name: 'Ann Claimant',
    guest_of_pass_id: 3,
  });

  const show = {
    id: 5,
    event_name: 'Existing Show',
    venue: { id: 1, name: 'Music Hall', venue_type: 'music' },
    show_date: '2099-12-31',
    status: 'published',
    available_pair_count: 1,
    available_staff_count: 0,
  } as ShowSummary;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(legacyImportAPI.checkEnabled).mockResolvedValue(true);
    vi.mocked(legacyImportAPI.listStaff).mockResolvedValue([]);
    vi.mocked(venuesAPI.list).mockResolvedValue([musicHall]);
    vi.mocked(showsAPI.list).mockResolvedValue([show]);
    vi.mocked(passesAPI.getForShow).mockResolvedValue([winner, openPair, claim, guestHold]);
  });

  const openExistingShow = async () => {
    await renderLegacyImport();
    fireEvent.click(screen.getByRole('button', { name: /add to existing show/i }));
    fireEvent.click(await screen.findByText('Existing Show'));
    await screen.findByText('Winner: Cal Caller');
  };

  it('lists one card per claim, without a separate card for the guest hold', async () => {
    await openExistingShow();

    expect(screen.getAllByRole('button', { name: /^release claimed by/i })).toHaveLength(1);
    expect(screen.getByText('+1 guest: Pat')).toBeInTheDocument();
  });

  it('releases a claim and shows who the next alternate is', async () => {
    vi.mocked(passesAPI.releaseClaim).mockResolvedValue({
      ...claim,
      staff_name: 'Bo Alternate',
      has_guest: false,
    });
    await openExistingShow();

    fireEvent.click(screen.getByRole('button', { name: /release claimed by ann claimant/i }));
    fireEvent.click(screen.getByRole('button', { name: /confirm release/i }));

    expect(await screen.findByText(/next alternate, bo alternate/i)).toBeInTheDocument();
    expect(passesAPI.releaseClaim).toHaveBeenCalledWith(3);
    expect(passesAPI.getForShow).toHaveBeenCalledTimes(2);
  });

  it('needs a reason to release a winner, then adds a row for the freed pass', async () => {
    vi.mocked(passesAPI.releaseWinner).mockResolvedValue({ ...winner, status: 'available' });
    await openExistingShow();
    expect(screen.getAllByLabelText(/winner name/i)).toHaveLength(1);
    fireEvent.change(screen.getByLabelText(/winner name/i), { target: { value: 'Typed Winner' } });

    fireEvent.click(screen.getByRole('button', { name: /release winner: cal caller/i }));
    const confirm = screen.getByRole('button', { name: /confirm release/i });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/reason/i), { target: { value: 'Cannot attend' } });
    vi.mocked(passesAPI.getForShow).mockResolvedValue([
      { ...winner, status: 'available', recipient_name: null },
      openPair,
      claim,
      guestHold,
    ]);
    fireEvent.click(confirm);

    expect(await screen.findByText(/released cal caller's passes/i)).toBeInTheDocument();
    expect(passesAPI.releaseWinner).toHaveBeenCalledWith(1, { reason: 'Cannot attend' });
    expect(screen.queryByText('Winner: Cal Caller')).not.toBeInTheDocument();
    const rows = screen.getAllByLabelText(/winner name/i);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveValue('Typed Winner');
  });

  it('shows the error and keeps the card when a release fails', async () => {
    vi.mocked(passesAPI.releaseClaim).mockRejectedValue({ detail: 'Cannot release passes for closed shows' });
    await openExistingShow();

    fireEvent.click(screen.getByRole('button', { name: /release claimed by ann claimant/i }));
    fireEvent.click(screen.getByRole('button', { name: /confirm release/i }));

    expect(await screen.findByText(/cannot release passes for closed shows/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /confirm release/i })).toBeEnabled();
    expect(passesAPI.getForShow).toHaveBeenCalledTimes(1);
  });
});
