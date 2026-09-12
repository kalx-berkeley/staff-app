import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import ShowDetail from './ShowDetail';
import { showsAPI, passesAPI, autocompleteAPI, specialtyShowsAPI, lotteryAPI } from '../../services/api';
import type { ShowResponse, PassResponse, DjSuggestion } from '../../types';

vi.mock('../../services/api', () => ({
  showsAPI: {
    get: vi.fn(),
  },
  passesAPI: {
    setPreassignment: vi.fn(),
    removePreassignment: vi.fn(),
    getPreassignSchedule: vi.fn().mockResolvedValue([]),
    getSuggestionsByDate: vi.fn(),
    getSuggestionsByGenre: vi.fn(),
  },
  autocompleteAPI: {
    getDJNames: vi.fn().mockResolvedValue([]),
  },
  specialtyShowsAPI: {
    list: vi.fn().mockResolvedValue([]),
  },
  lotteryAPI: {
    getStatus: vi.fn().mockResolvedValue({
      is_active: false,
      deadline: null,
      staff_entry_count: 0,
      dj_entry_count: 0,
      my_staff_entry: null,
      my_dj_entry: null,
    }),
  },
}));

vi.mock('../../contexts/authHooks', () => ({
  useAuth: () => ({ user: null, loading: false, error: null, refetchUser: vi.fn() }),
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useParams: () => ({ id: '1' }),
    useNavigate: () => vi.fn(),
  };
});

const basePass: PassResponse = {
  id: 1,
  show_id: 1,
  pass_type: 'pair',
  status: 'available',
  recipient_name: null,
  recipient_phone: null,
  recipient_email: null,
  given_away_by_dj: null,
  given_away_at: null,
  staff_id: null,
  staff_name: null,
  staff_phone: null,
  staff_email: null,
  claimed_at: null,
  has_guest: false,
  guest_name: null,
  only_attend_with_guest: false,
  guest_of_pass_id: null,
  preassigned_dj: null,
  preassigned_date: null,
  preassigned_specialty_show_id: null,
  preassigned_specialty_show_name: null,
  show_event_name: null,
  show_date: null,
  show_venue_name: null,
};

const makeShow = (passes: PassResponse[]): ShowResponse => ({
  id: 1,
  event_name: 'Test Concert',
  genre: ['Rock'],
  venue: {
    id: 1,
    name: 'Test Venue',
    address: '123 Main St',
    pass_call_instructions: null,
    win_frequency_days: null,
    default_wheelchair_accessible: null,
    default_age_restriction: null,
    default_num_pass_pairs: null,
    requires_phone_number: false,
    requires_email_address: false,
    staff_guest_requires_name: false,
    default_lottery_enabled: false,
    default_lottery_window_hours: 24,
    default_dj_preassign_prohibition_days: null,
    default_close_hours_before_show: null,
    has_logo: false,
    deleted: false,
    shows_have_external_promoter: false,
    owner_emails: [],
    contacts: [],
  },
  show_date: '2099-12-31',
  show_time: '20:00',
  show_start_date: null,
  on_air_description: null,
  caller_special_instructions: null,
  age_restriction: '21+',
  wheelchair_accessible: true,
  num_pass_pairs: passes.length,
  promotions_contacts: [],
  attempts: [],
  status: 'published',
  passes,
  available_pair_count: passes.filter((p) => p.status === 'available').length,
  available_staff_count: 0,
  planned_close_date: null,
  planned_close_time: null,
  auto_close: false,
  co_announce: false,
  lottery_enabled: false,
  lottery_window_hours: 24,
  dj_preassign_prohibition_days: null,
  published_at: null,
  bands: [],
  is_mine: false,
  in_feature_bin: false,
  feature_bin_releases: [],
});

const renderShowDetail = () =>
  render(
    <BrowserRouter>
      <ShowDetail />
    </BrowserRouter>
  );

// Pass pairs render "Pre-assign to DJ" buttons in array order, and each test's
// pass ids are assigned sequentially starting at 1, so `passId - 1` indexes
// the right button.
const openPreassignForm = async (passId: number) => {
  const buttons = await screen.findAllByRole('button', { name: 'Pre-assign to DJ' });
  fireEvent.click(buttons[passId - 1]);
};

describe('Promotions ShowDetail — Suggest DJs', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(autocompleteAPI.getDJNames).mockResolvedValue([]);
    vi.mocked(specialtyShowsAPI.list).mockResolvedValue([]);
    vi.mocked(passesAPI.getPreassignSchedule).mockResolvedValue([]);
    vi.mocked(lotteryAPI.getStatus).mockResolvedValue({
      is_active: false,
      deadline: null,
      staff_entry_count: 0,
      dj_entry_count: 0,
      my_staff_entry: null,
      my_dj_entry: null,
    });
  });

  it('shows a choice between suggesting by date or by genre', async () => {
    const show = makeShow([{ ...basePass, id: 1 }]);
    vi.mocked(showsAPI.get).mockResolvedValue(show);

    renderShowDetail();
    await openPreassignForm(1);

    fireEvent.click(await screen.findByRole('button', { name: 'Suggest…' }));

    expect(screen.getByRole('button', { name: 'Suggest DJs by date' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Suggest DJs by genre' })).toBeInTheDocument();
  });

  it('suggests by genre, saves the accepted suggestion, and advances to the next pass pair', async () => {
    const passA = { ...basePass, id: 1 };
    const passB = { ...basePass, id: 2 };
    const show = makeShow([passA, passB]);
    vi.mocked(showsAPI.get).mockResolvedValue(show);

    const suggestions: DjSuggestion[] = [
      { name: 'Wolfman', is_specialty: false, matched_genres: ['rock'] },
      { name: 'Sunday Jazz Brunch', is_specialty: true, matched_genres: ['rock'] },
    ];
    vi.mocked(passesAPI.getSuggestionsByGenre).mockResolvedValue(suggestions);
    vi.mocked(passesAPI.setPreassignment).mockResolvedValue({
      ...passA,
      preassigned_dj: 'Wolfman',
      preassigned_date: '2099-12-20',
    });

    renderShowDetail();
    await openPreassignForm(1);

    // Set a date up front so the accepted genre suggestion can be auto-saved.
    const dateInput = screen.getByPlaceholderText('MM/DD/YYYY');
    fireEvent.change(dateInput, { target: { value: '12/20/2099' } });

    fireEvent.click(screen.getByRole('button', { name: 'Suggest…' }));
    fireEvent.click(screen.getByRole('button', { name: 'Suggest DJs by genre' }));

    await waitFor(() => {
      expect(passesAPI.getSuggestionsByGenre).toHaveBeenCalledWith(1);
    });

    const wolfmanOption = await screen.findByText('Wolfman');
    fireEvent.click(wolfmanOption);

    await waitFor(() => {
      expect(passesAPI.setPreassignment).toHaveBeenCalledWith(1, {
        dj_name: 'Wolfman',
        assignment_date: '2099-12-20',
      });
    });

    // Advances to the second pass pair's suggest-by-genre panel, with Wolfman
    // no longer offered there (already used, though still shown as the first
    // pass pair's "Pre-assigned to" name) — only the specialty show remains.
    await waitFor(() => {
      expect(document.querySelector('.suggestion-list')).not.toBeNull();
    });
    const suggestionList = document.querySelector('.suggestion-list') as HTMLElement;
    expect(within(suggestionList).getByText('Sunday Jazz Brunch')).toBeInTheDocument();
    expect(within(suggestionList).queryByText('Wolfman')).not.toBeInTheDocument();
  });

  it('suggests by date, prompting for a date first when none is set, then saves and closes when no more pass pairs are available', async () => {
    const passA = { ...basePass, id: 1 };
    const show = makeShow([passA]);
    vi.mocked(showsAPI.get).mockResolvedValue(show);

    const suggestions: DjSuggestion[] = [
      { name: 'Nightowl', is_specialty: false, matched_genres: [] },
    ];
    vi.mocked(passesAPI.getSuggestionsByDate).mockResolvedValue(suggestions);
    vi.mocked(passesAPI.setPreassignment).mockResolvedValue({
      ...passA,
      status: 'available',
      preassigned_dj: 'Nightowl',
      preassigned_date: '2099-12-20',
    });

    renderShowDetail();
    await openPreassignForm(1);

    fireEvent.click(screen.getByRole('button', { name: 'Suggest…' }));
    fireEvent.click(screen.getByRole('button', { name: 'Suggest DJs by date' }));

    // No date set yet — the calendar UI is shown before any suggestions load.
    expect(passesAPI.getSuggestionsByDate).not.toHaveBeenCalled();
    const dateInput = screen.getByPlaceholderText('MM/DD/YYYY');
    fireEvent.change(dateInput, { target: { value: '12/20/2099' } });

    await waitFor(() => {
      expect(passesAPI.getSuggestionsByDate).toHaveBeenCalledWith('2099-12-20');
    });

    const nightowlOption = await screen.findByText('Nightowl');
    fireEvent.click(nightowlOption);

    await waitFor(() => {
      expect(passesAPI.setPreassignment).toHaveBeenCalledWith(1, {
        dj_name: 'Nightowl',
        assignment_date: '2099-12-20',
      });
    });

    // Only one pass pair existed — the form closes instead of advancing.
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'Back' })).not.toBeInTheDocument();
    });
  });

  it('genre suggestion with no date set fills the DJ name and exits suggest mode for manual date entry', async () => {
    const passA = { ...basePass, id: 1 };
    const show = makeShow([passA]);
    vi.mocked(showsAPI.get).mockResolvedValue(show);

    const suggestions: DjSuggestion[] = [
      { name: 'Wolfman', is_specialty: false, matched_genres: ['rock'] },
    ];
    vi.mocked(passesAPI.getSuggestionsByGenre).mockResolvedValue(suggestions);

    renderShowDetail();
    await openPreassignForm(1);

    fireEvent.click(screen.getByRole('button', { name: 'Suggest…' }));
    fireEvent.click(screen.getByRole('button', { name: 'Suggest DJs by genre' }));

    const wolfmanOption = await screen.findByText('Wolfman');
    fireEvent.click(wolfmanOption);

    expect(passesAPI.setPreassignment).not.toHaveBeenCalled();
    await waitFor(() => {
      const input = screen.getByPlaceholderText('DJ Name') as HTMLInputElement;
      expect(input.value).toBe('Wolfman');
    });
  });
});
