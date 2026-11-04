import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent, waitFor, within } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { renderAndSettle } from '../../test/render';
import ShowDetail from './ShowDetail';
import { showsAPI, passesAPI, autocompleteAPI, specialtyShowsAPI, lotteryAPI, alternatesAPI } from '../api';
import type { ShowResponse, PassResponse, DjSuggestion } from '../types';

vi.mock('../api', () => ({
  showsAPI: {
    get: vi.fn(),
    sendCloseNotifications: vi.fn(),
  },
  passesAPI: {
    setPreassignment: vi.fn(),
    removePreassignment: vi.fn(),
    removeGuest: vi.fn(),
    getPreassignSchedule: vi.fn().mockResolvedValue([]),
    getPreassignLeave: vi.fn().mockResolvedValue(null),
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
  alternatesAPI: {
    getQueue: vi.fn().mockResolvedValue({
      queue_open: false,
      entries: [],
      my_entry_id: null,
      next_candidate_staff_id: null,
      next_candidate_name: null,
      my_outcome_pending: false,
    }),
    remove: vi.fn(),
  },
}));

vi.mock('../../common/contexts/authHooks', () => ({
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
  guest_fallback: 'attend_alone' as const,
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
    show_sourcing_instructions: null,
    pass_call_instructions: null,
    win_frequency_days: null,
    default_wheelchair_accessible: null,
    venue_type: 'music', default_age_restriction: null, default_movie_rating: null,
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
  movie_rating: null,
  wheelchair_accessible: 'yes',
  num_pass_pairs: passes.length,
  extra_staff_passes: 0,
  num_staff_passes: passes.length,
  promotions_contacts: [],
  guest_list_requirements: { requires_phone_number: false, email_address_requirement: 'none', requires_email_address: false, staff_guest_requires_name: false },
  attempts: [],
  status: 'published',
  passes,
  available_pair_count: passes.filter((p) => p.status === 'available').length,
  available_staff_count: 0,
  planned_close_date: null,
  planned_close_time: null,
  auto_close: false,
  close_notifications_pending: false,
  close_notifications_sent_at: null,
  close_notifications_sent_by: null,
  co_announce: false,
  lottery_enabled: false,
  lottery_window_hours: 24,
  dj_preassign_prohibition_days: null,
  published_at: null,
  bands: [],
  is_mine: false,
  in_feature_bin: false,
  feature_bin_releases: [],
  on_kalx_live: false,
  kalx_live_appearances: [],
});

const renderShowDetail = () =>
  renderAndSettle(
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
    vi.mocked(passesAPI.getPreassignLeave).mockResolvedValue(null);
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

    await renderShowDetail();
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

    await renderShowDetail();
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

    // Advances to the second pass pair with a fresh form: no suggestion
    // mode, date or DJ carried over from the first.
    expect(await screen.findByRole('button', { name: 'Suggest…' })).toBeInTheDocument();
    expect(document.querySelector('.suggestion-list')).toBeNull();
    expect(screen.getByPlaceholderText('MM/DD/YYYY')).toHaveValue('');
  });

  it('suggests by date, then advances to the next pass pair with a fresh form', async () => {
    const passA = { ...basePass, id: 1 };
    const passB = { ...basePass, id: 2 };
    const show = makeShow([passA, passB]);
    vi.mocked(showsAPI.get).mockResolvedValue(show);

    vi.mocked(passesAPI.getSuggestionsByDate).mockResolvedValue([
      { name: 'Nightowl', is_specialty: false, matched_genres: [] },
      { name: 'Wolfman', is_specialty: false, matched_genres: [] },
    ]);
    vi.mocked(passesAPI.setPreassignment).mockResolvedValue({
      ...passA,
      preassigned_dj: 'Nightowl',
      preassigned_date: '2099-12-20',
    });

    await renderShowDetail();
    await openPreassignForm(1);

    fireEvent.click(screen.getByRole('button', { name: 'Suggest…' }));
    fireEvent.click(screen.getByRole('button', { name: 'Suggest DJs by date' }));
    fireEvent.change(screen.getByPlaceholderText('MM/DD/YYYY'), {
      target: { value: '12/20/2099' },
    });
    fireEvent.click(await screen.findByText('Nightowl'));

    await waitFor(() => {
      expect(passesAPI.setPreassignment).toHaveBeenCalledWith(1, {
        dj_name: 'Nightowl',
        assignment_date: '2099-12-20',
      });
    });

    expect(await screen.findByRole('button', { name: 'Suggest…' })).toBeInTheDocument();
    expect(document.querySelector('.suggestion-list')).toBeNull();
    expect(screen.queryByText('Wolfman')).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText('MM/DD/YYYY')).toHaveValue('');
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

    await renderShowDetail();
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

    await renderShowDetail();
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

describe('Promotions ShowDetail — leave of absence', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('labels a claimant whose leave covers the show', async () => {
    const staffPass: PassResponse = {
      ...basePass,
      id: 1,
      pass_type: 'staff',
      status: 'claimed',
      staff_id: 7,
      staff_name: 'Away Person',
      staff_on_leave: true,
      staff_loa_start: '2099-12-01',
      staff_loa_end: null,
    };
    vi.mocked(showsAPI.get).mockResolvedValue(makeShow([staffPass]));

    await renderShowDetail();

    expect(await screen.findByText('On leave from Dec 1, 2099')).toBeInTheDocument();
  });

  it('labels genre suggestions for DJs on leave', async () => {
    vi.mocked(showsAPI.get).mockResolvedValue(makeShow([{ ...basePass, id: 1 }]));
    vi.mocked(passesAPI.getSuggestionsByGenre).mockResolvedValue([
      { name: 'Wolfman', is_specialty: false, matched_genres: ['rock'] },
      {
        name: 'Away DJ',
        is_specialty: false,
        matched_genres: ['rock'],
        on_leave: true,
        loa_start: '2099-11-01',
        loa_end: '2099-12-31',
      },
    ]);

    await renderShowDetail();
    await openPreassignForm(1);
    fireEvent.click(screen.getByRole('button', { name: 'Suggest…' }));
    fireEvent.click(screen.getByRole('button', { name: 'Suggest DJs by genre' }));

    expect(
      await screen.findByText('On leave Nov 1, 2099 – Dec 31, 2099'),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/On leave/)).toHaveLength(1);
  });
});

describe('Promotions ShowDetail — staff +1 guests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows a +1 guest hold as the claimant\'s guest, not a second claim', async () => {
    const claimed = { ...basePass, pass_type: 'staff' as const, status: 'claimed' as const, staff_id: 7, staff_name: 'John Doe' };
    vi.mocked(showsAPI.get).mockResolvedValue(
      makeShow([
        { ...claimed, id: 1, has_guest: true },
        { ...claimed, id: 2, guest_of_pass_id: 1 },
      ]),
    );

    await renderShowDetail();

    expect(await screen.findByText(/\+1 guest reserved/)).toBeInTheDocument();
    expect(screen.getAllByText('Claimed by:')).toHaveLength(1);
    expect(screen.getByText('+1 guest hold')).toBeInTheDocument();
    expect(screen.getByText('+1 guest of:').parentElement).toHaveTextContent('+1 guest of: John Doe');
  });
});

describe('Promotions ShowDetail — guest list', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const closedShow = (emailAddressRequirement: 'none' | 'staff_passes' | 'all') => {
    const staff = { ...basePass, pass_type: 'staff' as const, status: 'claimed' as const };
    const show = makeShow([
      {
        ...basePass, id: 1, status: 'given_away', recipient_name: 'Caller',
        recipient_phone: '5551234567', recipient_email: 'caller@example.com',
      },
      { ...staff, id: 2, staff_id: 7, staff_name: 'Solo', staff_email: 'solo@example.com' },
      { ...staff, id: 3, staff_id: 8, staff_name: 'John Doe', staff_email: 'john@example.com', has_guest: true },
      { ...staff, id: 4, staff_id: 8, staff_name: 'John Doe', guest_of_pass_id: 3 },
    ]);
    return {
      ...show,
      status: 'closed' as const,
      guest_list_requirements: {
        ...show.guest_list_requirements,
        email_address_requirement: emailAddressRequirement,
      },
    };
  };

  it('counts a staff member and their guest as a pair of passes', async () => {
    vi.mocked(showsAPI.get).mockResolvedValue(closedShow('none'));

    await renderShowDetail();

    expect((await screen.findByText(/1 pair of passes for Caller/)).textContent).toBe(
      [
        '1 pair of passes for Caller and a guest',
        '1 pass for Solo',
        '1 pair of passes for John Doe and a guest',
      ].join('\n'),
    );
  });

  it('includes only staff pass winners\' email addresses when the show\'s promoter or venue wants just those', async () => {
    vi.mocked(showsAPI.get).mockResolvedValue(closedShow('staff_passes'));

    await renderShowDetail();

    const list = await screen.findByText(/1 pair of passes for Caller/);
    expect(list).toHaveTextContent('1 pass for Solo (solo@example.com)');
    expect(list).toHaveTextContent('John Doe and a guest (john@example.com)');
    expect(list).not.toHaveTextContent('caller@example.com');
  });

  it('includes every winner\'s email address when the show\'s promoter or venue wants them all', async () => {
    vi.mocked(showsAPI.get).mockResolvedValue(closedShow('all'));

    await renderShowDetail();

    const list = await screen.findByText(/1 pair of passes for Caller/);
    expect(list).toHaveTextContent('Caller and a guest (caller@example.com)');
    expect(list).toHaveTextContent('1 pass for Solo (solo@example.com)');
  });
});

describe('Promotions ShowDetail — alternates', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('lists alternates and removes one after confirmation', async () => {
    const staffPass: PassResponse = {
      ...basePass,
      id: 2,
      pass_type: 'staff',
      status: 'claimed',
      staff_name: 'Holder',
    };
    vi.mocked(showsAPI.get).mockResolvedValue(makeShow([staffPass]));
    const alt = {
      id: 7,
      show_id: 1,
      staff_id: 30,
      staff_name: 'Wanda Waiting',
      staff_phone: '5551234567',
      staff_email: 'wanda@example.com',
      position: 1,
      has_guest: false,
      guest_name: null,
      guest_fallback: 'attend_alone' as const,
      source: 'lottery',
      priority_at: '2024-01-01T00:00:00Z',
    };
    vi.mocked(alternatesAPI.getQueue)
      .mockResolvedValueOnce({
        queue_open: true,
        entries: [alt],
        my_entry_id: null,
        next_candidate_staff_id: null,
        next_candidate_name: null,
        my_outcome_pending: false,
      })
      .mockResolvedValue({
        queue_open: true,
        entries: [],
        my_entry_id: null,
        next_candidate_staff_id: null,
        next_candidate_name: null,
        my_outcome_pending: false,
      });
    vi.mocked(alternatesAPI.remove).mockResolvedValue(undefined);

    await renderShowDetail();

    expect(await screen.findByText('Alternate #1')).toBeInTheDocument();
    expect(screen.getByText('Wanda Waiting')).toBeInTheDocument();
    const card = screen.getByText('Alternate #1').closest('.alternate-card') as HTMLElement;
    expect(within(card).getByText('Phone:').parentElement).toHaveTextContent('(555) 123-4567');
    expect(within(card).getByText('Waiting since:').parentElement).toHaveTextContent('Dec 31, 4:00 PM');
    // This venue doesn't ask for email addresses.
    expect(within(card).queryByText('Email:')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Remove' }));
    const dialog = screen.getByRole('heading', { name: 'Remove Alternate' }).closest('.modal-content') as HTMLElement;
    expect(within(dialog).getByText(/they will be emailed/i)).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole('button', { name: 'Remove' }));

    await waitFor(() => expect(alternatesAPI.remove).toHaveBeenCalledWith(1, 7));
    await waitFor(() => expect(screen.queryByText('Alternate #1')).not.toBeInTheDocument());
  });

  it("shows alternates' email addresses when the venue requires them", async () => {
    const show = makeShow([]);
    vi.mocked(showsAPI.get).mockResolvedValue({
      ...show,
      guest_list_requirements: {
        ...show.guest_list_requirements,
        email_address_requirement: 'staff_passes',
      },
    });
    vi.mocked(alternatesAPI.getQueue).mockResolvedValue({
      queue_open: true,
      entries: [
        {
          id: 7,
          show_id: 1,
          staff_id: 30,
          staff_name: 'Wanda Waiting',
          staff_phone: '5551234567',
          staff_email: 'wanda@example.com',
          position: 1,
          has_guest: false,
          guest_name: null,
          guest_fallback: 'attend_alone' as const,
          source: 'joined',
          priority_at: '2024-01-01T00:00:00Z',
        },
      ],
      my_entry_id: null,
      next_candidate_staff_id: null,
      next_candidate_name: null,
      my_outcome_pending: false,
    });

    await renderShowDetail();

    const label = await screen.findByText('Email:');
    expect(label.closest('.alternate-card')).toHaveTextContent('wanda@example.com');
  });

  describe('waiting guests', () => {
    const waitingQueue = {
      queue_open: false,
      entries: [],
      waiting_guests: [
        {
          pass_id: 12,
          position: 1,
          guest_name: 'Sam',
          host_staff_id: 30,
          host_name: 'Alex',
          is_mine: false,
        },
      ],
      my_entry_id: null,
      next_candidate_staff_id: null,
      next_candidate_name: null,
      my_outcome_pending: false,
    };

    it('lets promotions staff remove a waiting guest', async () => {
      vi.mocked(showsAPI.get).mockResolvedValue({ ...makeShow([]), status: 'published' });
      vi.mocked(alternatesAPI.getQueue).mockResolvedValue(waitingQueue);
      vi.mocked(passesAPI.removeGuest).mockResolvedValue({} as PassResponse);

      await renderShowDetail();

      expect(await screen.findByText('Sam (guest of Alex)')).toBeInTheDocument();
      fireEvent.click(screen.getByRole('button', { name: /^remove$/i }));
      expect(screen.getByText(/emailed that you removed their guest/i)).toBeInTheDocument();
      const [, confirm] = screen.getAllByRole('button', { name: /^remove$/i });
      fireEvent.click(confirm);

      await waitFor(() => expect(passesAPI.removeGuest).toHaveBeenCalledWith(12));
      await waitFor(() => expect(showsAPI.get).toHaveBeenCalledTimes(2));
    });

    it('says a seated guest is confirmed once the show has closed', async () => {
      const host = {
        ...makeShow([]).passes[0],
        id: 20,
        pass_type: 'staff' as const,
        status: 'claimed' as const,
        staff_id: 30,
        staff_name: 'Alex',
        staff_phone: '5551234567',
        has_guest: true,
        guest_name: 'Sam',
      };
      vi.mocked(showsAPI.get).mockResolvedValue({
        ...makeShow([host]),
        status: 'closed',
        close_notifications_pending: false,
      });
      vi.mocked(alternatesAPI.getQueue).mockResolvedValue({ ...waitingQueue, waiting_guests: [] });

      await renderShowDetail();

      expect(await screen.findByText('confirmed')).toBeInTheDocument();
      expect(screen.queryByText(/until show closes/i)).not.toBeInTheDocument();
    });

    it('marks staff released at close in the closed alternates list', async () => {
      vi.mocked(showsAPI.get).mockResolvedValue({ ...makeShow([]), status: 'closed' });
      vi.mocked(alternatesAPI.getQueue).mockResolvedValue({
        ...waitingQueue,
        waiting_guests: [],
        entries: [
          {
            id: 7,
            show_id: 1,
            staff_id: 30,
            staff_name: 'Alex',
            staff_phone: null,
            staff_email: null,
            position: 1,
            has_guest: true,
            guest_name: 'Sam',
            guest_fallback: 'wait_then_release' as const,
            source: 'released_at_close',
            priority_at: '2024-01-01T00:00:00Z',
          },
        ],
      });

      await renderShowDetail();

      expect(await screen.findByText(/pass released at close/i)).toBeInTheDocument();
    });

    it('lists guests still waiting below the guest list once closed', async () => {
      vi.mocked(showsAPI.get).mockResolvedValue({ ...makeShow([]), status: 'closed' });
      vi.mocked(alternatesAPI.getQueue).mockResolvedValue(waitingQueue);

      await renderShowDetail();

      expect(await screen.findByText('Guests still waiting (1)')).toBeInTheDocument();
      expect(screen.getByText('Sam (guest of Alex)')).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /^remove$/i })).not.toBeInTheDocument();
    });
  });

  describe('on a closed show', () => {
    const closedQueue = {
      queue_open: false,
      entries: [
        {
          id: 7,
          show_id: 1,
          staff_id: 30,
          staff_name: 'Wanda Waiting',
          staff_phone: '5551234567',
          staff_email: 'wanda@example.com',
          position: 1,
          has_guest: false,
          guest_name: null,
          guest_fallback: 'attend_alone' as const,
          source: 'joined',
          priority_at: '2024-01-01T00:00:00Z',
        },
      ],
      my_entry_id: null,
      next_candidate_staff_id: null,
      next_candidate_name: null,
      my_outcome_pending: false,
    };

    it('lists them once, in their own panel right after the guest list, without Remove', async () => {
      vi.mocked(showsAPI.get).mockResolvedValue({ ...makeShow([]), status: 'closed' });
      vi.mocked(alternatesAPI.getQueue).mockResolvedValue(closedQueue);

      await renderShowDetail();

      const heading = await screen.findByRole('heading', { name: 'Alternates (1)' });
      const panel = heading.closest('.guest-list-summary') as HTMLElement;
      const guestList = screen
        .getByRole('heading', { name: 'Guest List for Venue' })
        .closest('.guest-list-summary') as HTMLElement;
      expect(panel).not.toBe(guestList);
      expect(guestList.nextElementSibling).toBe(panel);
      expect(within(panel).getByText('Alternate #1')).toBeInTheDocument();
      expect(screen.getAllByText('Alternate #1')).toHaveLength(1);
      expect(within(guestList).queryByText(/Wanda Waiting/)).not.toBeInTheDocument();
      expect(within(panel).queryByRole('button', { name: 'Remove' })).not.toBeInTheDocument();
    });

    it('has no panel when there were no alternates', async () => {
      vi.mocked(showsAPI.get).mockResolvedValue({ ...makeShow([]), status: 'closed' });
      vi.mocked(alternatesAPI.getQueue).mockResolvedValue({ ...closedQueue, entries: [] });

      await renderShowDetail();

      await screen.findByRole('heading', { name: 'Guest List for Venue' });
      await waitFor(() => expect(alternatesAPI.getQueue).toHaveBeenCalled());
      expect(screen.queryByRole('heading', { name: /^Alternates/ })).not.toBeInTheDocument();
    });
  });

  describe('Close notifications button', () => {
    const hostPass = {
      id: 7,
      pass_type: 'staff',
      status: 'claimed',
      has_guest: true,
      staff_name: 'Hana Host',
    } as PassResponse;
    const waiting = {
      queue_open: false,
      entries: [
        {
          id: 40,
          show_id: 1,
          staff_id: 30,
          staff_name: 'Wanda Waiting',
          staff_phone: null,
          staff_email: null,
          position: 1,
          has_guest: false,
          guest_name: null,
          guest_fallback: 'attend_alone' as const,
          source: 'joined',
          priority_at: '2024-01-01T00:00:00Z',
        },
      ],
      my_entry_id: null,
      next_candidate_staff_id: null,
      next_candidate_name: null,
      my_outcome_pending: false,
    };
    const guestListPanel = () =>
      screen
        .getByRole('heading', { name: 'Guest List for Venue' })
        .closest('.guest-list-summary') as HTMLElement;

    it('hides the button when nothing is pending', async () => {
      vi.mocked(showsAPI.get).mockResolvedValue({ ...makeShow([]), status: 'closed' });

      await renderShowDetail();

      await screen.findByRole('heading', { name: 'Guest List for Venue' });
      expect(
        screen.queryByRole('button', { name: 'Notify Staff and Alternates' })
      ).not.toBeInTheDocument();
    });

    it('leaves an empty group out of the confirmation', async () => {
      vi.mocked(showsAPI.get).mockResolvedValue({
        ...makeShow([]),
        status: 'closed',
        close_notifications_pending: true,
      });
      vi.mocked(alternatesAPI.getQueue).mockResolvedValue(waiting);

      await renderShowDetail();

      await screen.findByRole('heading', { name: 'Alternates (1)' });
      fireEvent.click(screen.getByRole('button', { name: 'Notify Staff and Alternates' }));

      const message = screen.getByText(/This will email/);
      expect(message).toHaveTextContent("This will email 1 alternate that they didn't get a pass for");
      expect(message).not.toHaveTextContent('host');
    });

    it('confirms who will be emailed, then sends and shows who sent them', async () => {
      const pending = {
        ...makeShow([hostPass]),
        status: 'closed',
        close_notifications_pending: true,
      } as ShowResponse;
      vi.mocked(showsAPI.get).mockResolvedValueOnce(pending).mockResolvedValue({
        ...pending,
        close_notifications_pending: false,
        close_notifications_sent_at: '2024-01-01T20:00:00Z',
        close_notifications_sent_by: 'Pat Promo',
      });
      vi.mocked(showsAPI.sendCloseNotifications).mockResolvedValue(pending);
      vi.mocked(alternatesAPI.getQueue).mockResolvedValue(waiting);

      await renderShowDetail();

      await screen.findByRole('heading', { name: 'Alternates (1)' });
      fireEvent.click(
        within(guestListPanel()).getByRole('button', { name: 'Notify Staff and Alternates' })
      );
      expect(screen.getByText(/email 1 \+1 host that/)).toHaveTextContent('1 alternate that');

      fireEvent.click(screen.getByRole('button', { name: 'Send Notifications' }));

      expect(await within(guestListPanel()).findByText(/by Pat Promo/)).toBeInTheDocument();
      expect(showsAPI.sendCloseNotifications).toHaveBeenCalledWith(1);
      expect(
        screen.queryByRole('button', { name: 'Notify Staff and Alternates' })
      ).not.toBeInTheDocument();
    });
  });
});
