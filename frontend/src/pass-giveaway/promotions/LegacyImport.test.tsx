import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import LegacyImport from './LegacyImport';
import { legacyImportAPI, venuesAPI } from '../api';
import { renderAndSettle } from '../../test/render';
import type { VenueResponse } from '../types';

vi.mock('../api', () => ({
  legacyImportAPI: {
    checkEnabled: vi.fn(),
    listStaff: vi.fn(),
    importShow: vi.fn(),
    mergeShow: vi.fn(),
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
  requires_email_address: false,
  staff_guest_requires_name: false,
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
