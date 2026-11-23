import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { renderAndSettle } from '../../test/render';
import { BrowserRouter } from 'react-router-dom';
import ShowDetail from './ShowDetail';
import { showsAPI, passesAPI, alternatesAPI } from '../api';
import type { ShowResponse, PassResponse, AlternateEntry, AlternateQueue, MyIdentity } from '../types';
import type { UserResponse } from '../../common/types';

// Mock the API
vi.mock('../api', () => ({
  showsAPI: {
    get: vi.fn(),
    getMyAgeChecks: vi.fn(),
  },
  passesAPI: {
    claim: vi.fn(),
    releaseClaim: vi.fn(),
    removePreassignment: vi.fn(),
    getMyPreassignIdentities: vi.fn(),
    selfPreassign: vi.fn(),
    addGuest: vi.fn(),
    updateGuestName: vi.fn(),
    removeGuest: vi.fn(),
  },
  alternatesAPI: {
    getQueue: vi.fn(),
    join: vi.fn(),
    updateMine: vi.fn(),
    leave: vi.fn(),
  },
}));

const mockUseAuth = vi.fn<() => { user: UserResponse | null; loading: boolean; error: string | null; refetchUser: () => Promise<void> }>(
  () => ({ user: null, loading: false, error: null, refetchUser: vi.fn() })
);
vi.mock('../../common/contexts/authHooks', () => ({
  useAuth: () => mockUseAuth(),
}));

// Mock useParams
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useParams: () => ({ id: '1' }),
    useNavigate: () => vi.fn(),
  };
});

describe('Staff ShowDetail', () => {
  const availablePass: PassResponse = {
    id: 1,
    show_id: 1,
    pass_type: 'staff',
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

  const claimedPass: PassResponse = {
    id: 2,
    show_id: 1,
    pass_type: 'staff',
    status: 'claimed',
    recipient_name: null,
    recipient_phone: null,
    recipient_email: null,
    given_away_by_dj: null,
    given_away_at: null,
    staff_id: 5,
    staff_name: 'Jane Staff',
    staff_phone: '555-999-0000',
    staff_email: 'jane@example.com',
    claimed_at: '2024-01-10T10:00:00',
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

  const mockShow: ShowResponse = {
    id: 1,
    event_name: 'Test Concert',
    genre: ['Rock'],
    venue: { id: 1, name: 'Test Venue', address: '123 Main St', show_sourcing_instructions: null, pass_call_instructions: null, win_frequency_days: null, default_wheelchair_accessible: null, venue_type: 'music', default_age_restriction: null, default_movie_rating: null, default_num_pass_pairs: null, requires_phone_number: false, email_address_requirement: 'none', requires_email_address: false, staff_guest_requires_name: false, hold_close_notifications: false, track_pass_call_in: false, default_lottery_enabled: false, default_lottery_window_hours: 24, default_dj_preassign_prohibition_days: null, default_close_hours_before_show: null, default_on_air_description: null, default_caller_special_instructions: null, default_staff_instructions: null, has_logo: false, show_name_with_logo: false, deleted: false, shows_have_external_promoter: false, owner_emails: [], owner_details: [], contacts: [] },
    show_date: '2024-12-31',
    show_time: '20:00',
    show_start_date: null,
    on_air_description: null,
    caller_special_instructions: null,
    staff_instructions: null,
    age_restriction: '21+',
    movie_rating: null,
    wheelchair_accessible: 'yes',
    num_pass_pairs: 2,
    staff_pass_adjustment: 0,
    num_staff_passes: 2,
    num_tabler_passes: 0,
    available_tabler_count: 0,
    tabler_open_days: 7,
    tabler_open_to_all_at: null,
    tablers: [],
    promotions_contacts: [],
    guest_list_requirements: { requires_phone_number: false, email_address_requirement: 'none', requires_email_address: false, staff_guest_requires_name: false },
    attempts: [],
    status: 'published',
    passes: [availablePass, claimedPass],
    available_pair_count: 0,
    available_staff_count: 1,
    planned_close_date: null,
    planned_close_time: null,
    planned_close_passed: false,
    auto_close: false,
    close_notifications_pending: false,
    close_notifications_sent_at: null,
    close_notifications_sent_by: null,
    track_pass_call_in: false,
    passes_called_in_at: null,
    passes_called_in_by: null,
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
  };

  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(passesAPI.getMyPreassignIdentities).mockResolvedValue([]);
    vi.mocked(showsAPI.getMyAgeChecks).mockResolvedValue({});
    mockUseAuth.mockReturnValue({ user: null, loading: false, error: null, refetchUser: vi.fn() });
  });

  // Only the claimer sees Release on their own pass.
  const loginAsClaimer = () =>
    mockUseAuth.mockReturnValue({
      user: { email: 'jane@example.com', role: 'staff', is_dj_network: false, is_station_office_network: false, profile: { id: 1, name: 'Jane Staff', phone: '555-999-0000', dj_name: null, is_sublist_dj: false } },
      loading: false,
      error: null,
      refetchUser: vi.fn(),
    });

  describe('Show Information Display', () => {
    it('should display show details correctly', async () => {
      vi.mocked(showsAPI.get).mockResolvedValue(mockShow);

      render(
        <BrowserRouter>
          <ShowDetail />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('Test Concert')).toBeInTheDocument();
        expect(screen.getByText('Rock')).toBeInTheDocument();
        expect(screen.getByText('Test Venue')).toBeInTheDocument();
        expect(screen.getByText('123 Main St')).toBeInTheDocument();
        expect(screen.getByText('21+')).toBeInTheDocument();
        expect(screen.getByText('Yes')).toBeInTheDocument();
      });
    });

    it('shows the staff instructions', async () => {
      vi.mocked(showsAPI.get).mockResolvedValue({
        ...mockShow,
        staff_instructions: 'Pick up at **will call**.',
      });

      render(
        <BrowserRouter>
          <ShowDetail />
        </BrowserRouter>
      );

      expect(await screen.findByText('Staff Instructions')).toBeInTheDocument();
      expect(await screen.findByText('will call')).toBeInTheDocument();
    });

    it('leaves out the staff instructions when there are none', async () => {
      vi.mocked(showsAPI.get).mockResolvedValue(mockShow);

      render(
        <BrowserRouter>
          <ShowDetail />
        </BrowserRouter>
      );

      expect(await screen.findByText('Test Concert')).toBeInTheDocument();
      expect(screen.queryByText('Staff Instructions')).not.toBeInTheDocument();
    });

    it('should display staff pass count in heading', async () => {
      vi.mocked(showsAPI.get).mockResolvedValue(mockShow);

      render(
        <BrowserRouter>
          <ShowDetail />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByText(/staff passes.*1 of 2 available/i)).toBeInTheDocument();
      });
    });
  });

  describe('Individual Pass Cards', () => {
    it('should say so and offer no lottery when a show has no staff passes', async () => {
      loginAsClaimer();
      vi.mocked(showsAPI.get).mockResolvedValue({
        ...mockShow,
        lottery_enabled: true,
        published_at: new Date().toISOString(),
        passes: mockShow.passes.filter((p) => p.pass_type !== 'staff'),
      });

      await renderAndSettle(
        <BrowserRouter>
          <ShowDetail />
        </BrowserRouter>
      );

      expect(await screen.findByText('This show has no staff passes.')).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /enter lottery/i })).not.toBeInTheDocument();
      expect(screen.queryByText(/lottery mode is active/i)).not.toBeInTheDocument();
    });

    it('should show Claim button for available passes', async () => {
      vi.mocked(showsAPI.get).mockResolvedValue(mockShow);

      render(
        <BrowserRouter>
          <ShowDetail />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /^claim$/i })).toBeInTheDocument();
      });
    });

    it('should show claimed staff name', async () => {
      vi.mocked(showsAPI.get).mockResolvedValue(mockShow);

      render(
        <BrowserRouter>
          <ShowDetail />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('Jane Staff')).toBeInTheDocument();
      });
    });

    it('should show Release button for claimed passes when show is published', async () => {
      loginAsClaimer();
      vi.mocked(showsAPI.get).mockResolvedValue(mockShow);

      render(
        <BrowserRouter>
          <ShowDetail />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /^release$/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /^release$/i })).not.toBeDisabled();
      });
    });

    it("should not show Release on someone else's claim", async () => {
      mockUseAuth.mockReturnValue({
        user: { email: 'other@example.com', role: 'staff', is_dj_network: false, is_station_office_network: false, profile: { id: 1, name: 'Other', phone: '555-0000', dj_name: null, is_sublist_dj: false } },
        loading: false,
        error: null,
        refetchUser: vi.fn(),
      });
      vi.mocked(showsAPI.get).mockResolvedValue(mockShow);

      render(
        <BrowserRouter>
          <ShowDetail />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('Jane Staff')).toBeInTheDocument();
      });
      expect(screen.queryByRole('button', { name: /^release$/i })).not.toBeInTheDocument();
    });

    it('should disable Release button when show is closed', async () => {
      loginAsClaimer();
      const closedShow = { ...mockShow, status: 'closed' as const };
      vi.mocked(showsAPI.get).mockResolvedValue(closedShow);

      render(
        <BrowserRouter>
          <ShowDetail />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /^release$/i })).toBeDisabled();
      });
    });
  });

  describe('Claim Pass', () => {
    it('should call claim API with the specific pass ID', async () => {
      vi.mocked(showsAPI.get).mockResolvedValue(mockShow);
      vi.mocked(passesAPI.claim).mockResolvedValue({
        ...availablePass,
        status: 'claimed',
        staff_name: 'Test User',
        claimed_at: '2024-01-01T12:00:00',
      });

      render(
        <BrowserRouter>
          <ShowDetail />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /^claim$/i })).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /^claim$/i }));

      await waitFor(() => {
        expect(passesAPI.claim).toHaveBeenCalledWith(1, undefined);
      });
    });

    it('should show success message after successful claim', async () => {
      vi.mocked(showsAPI.get).mockResolvedValue(mockShow);
      vi.mocked(passesAPI.claim).mockResolvedValue({
        ...availablePass,
        status: 'claimed',
      });

      render(
        <BrowserRouter>
          <ShowDetail />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /^claim$/i })).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /^claim$/i }));

      await waitFor(() => {
        expect(screen.getByText('Pass claimed successfully!')).toBeInTheDocument();
      });
    });

    it('sends the chosen guest fallback when claiming with a +1', async () => {
      vi.mocked(showsAPI.get).mockResolvedValue({
        ...mockShow,
        passes: [availablePass, { ...availablePass, id: 3 }],
      });
      vi.mocked(passesAPI.claim).mockResolvedValue({
        ...availablePass,
        status: 'claimed',
      });

      render(
        <BrowserRouter>
          <ShowDetail />
        </BrowserRouter>
      );

      const [claimWithGuest] = await screen.findAllByRole('button', {
        name: /claim with \+1 guest/i,
      });
      fireEvent.click(claimWithGuest);
      fireEvent.click(screen.getByRole('radio', { name: /release my pass too/i }));
      fireEvent.click(screen.getByRole('button', { name: /^claim with \+1$/i }));

      expect(
        await screen.findByText('Pass claimed with +1 guest reservation!')
      ).toBeInTheDocument();
      expect(passesAPI.claim).toHaveBeenCalledWith(availablePass.id, {
        has_guest: true,
        guest_name: null,
        guest_fallback: 'release',
      });
    });

    it('should show error message when claim fails', async () => {
      vi.mocked(showsAPI.get).mockResolvedValue(mockShow);
      vi.mocked(passesAPI.claim).mockRejectedValue({
        detail: 'All passes have been claimed',
      });

      render(
        <BrowserRouter>
          <ShowDetail />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /^claim$/i })).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /^claim$/i }));

      await waitFor(() => {
        expect(screen.getByText('All passes have been claimed')).toBeInTheDocument();
      });
    });

    it('should reload show data after successful claim', async () => {
      const updatedShow = {
        ...mockShow,
        available_staff_count: 0,
        passes: [
          { ...availablePass, status: 'claimed' as const, staff_name: 'Test User' },
          claimedPass,
        ],
      };

      vi.mocked(showsAPI.get)
        .mockResolvedValueOnce(mockShow)
        .mockResolvedValueOnce(updatedShow);

      vi.mocked(passesAPI.claim).mockResolvedValue({
        ...availablePass,
        status: 'claimed',
      });

      render(
        <BrowserRouter>
          <ShowDetail />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /^claim$/i })).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /^claim$/i }));

      await waitFor(() => {
        expect(showsAPI.get).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('One pass per staff member', () => {
    it('disables Claim on other passes once the current user already has one', async () => {
      const secondAvailablePass: PassResponse = {
        ...availablePass,
        id: 3,
      };
      const myClaimedPass: PassResponse = {
        ...claimedPass,
        id: 4,
        staff_email: 'me@example.com',
      };
      const showWithMyClaim = {
        ...mockShow,
        passes: [secondAvailablePass, myClaimedPass],
      };
      mockUseAuth.mockReturnValue({
        user: { email: 'me@example.com', role: 'staff', is_dj_network: false, is_station_office_network: false, profile: { id: 1, name: 'Me', phone: '555-0000', dj_name: null, is_sublist_dj: false } },
        loading: false,
        error: null,
        refetchUser: vi.fn(),
      });
      vi.mocked(showsAPI.get).mockResolvedValue(showWithMyClaim);

      render(
        <BrowserRouter>
          <ShowDetail />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /^claim$/i })).toBeDisabled();
      });
      expect(
        screen.getByText(/you already have a staff pass for this show/i)
      ).toBeInTheDocument();
    });

    it('links to My Passes when the current user has a staff pass for this show', async () => {
      loginAsClaimer();
      vi.mocked(showsAPI.get).mockResolvedValue(mockShow);

      await renderAndSettle(
        <BrowserRouter>
          <ShowDetail />
        </BrowserRouter>
      );

      expect(await screen.findByRole('note')).toHaveTextContent(
        /you have a staff pass for this show/i
      );
      expect(screen.getByRole('link', { name: /my passes/i })).toHaveAttribute(
        'href',
        '/staff/my-passes'
      );
    });

    it('links to My Passes when the current user has a tabler pass for this show', async () => {
      loginAsClaimer();
      vi.mocked(showsAPI.get).mockResolvedValue({
        ...mockShow,
        passes: [availablePass, { ...claimedPass, pass_type: 'tabler' as const }],
      });

      await renderAndSettle(
        <BrowserRouter>
          <ShowDetail />
        </BrowserRouter>
      );

      expect(await screen.findByRole('note')).toHaveTextContent(
        /you have a tabler pass for this show/i
      );
      expect(screen.getByRole('link', { name: /my passes/i })).toHaveAttribute(
        'href',
        '/staff/my-passes'
      );
    });

    it("doesn't link to My Passes when the current user has no pass for this show", async () => {
      mockUseAuth.mockReturnValue({
        user: { email: 'someone-else@example.com', role: 'staff', is_dj_network: false, is_station_office_network: false, profile: { id: 1, name: 'Someone Else', phone: '555-0000', dj_name: null, is_sublist_dj: false } },
        loading: false,
        error: null,
        refetchUser: vi.fn(),
      });
      vi.mocked(showsAPI.get).mockResolvedValue(mockShow);

      await renderAndSettle(
        <BrowserRouter>
          <ShowDetail />
        </BrowserRouter>
      );

      await screen.findByRole('button', { name: /^claim$/i });
      expect(screen.queryByRole('link', { name: /my passes/i })).not.toBeInTheDocument();
    });

    it('leaves Claim enabled for a user with no existing pass on this show', async () => {
      mockUseAuth.mockReturnValue({
        user: { email: 'someone-else@example.com', role: 'staff', is_dj_network: false, is_station_office_network: false, profile: { id: 1, name: 'Someone Else', phone: '555-0000', dj_name: null, is_sublist_dj: false } },
        loading: false,
        error: null,
        refetchUser: vi.fn(),
      });
      vi.mocked(showsAPI.get).mockResolvedValue(mockShow);

      render(
        <BrowserRouter>
          <ShowDetail />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /^claim$/i })).not.toBeDisabled();
      });
    });
  });

  describe('Leave of absence', () => {
    const onLeave = (loa_start: string | null, loa_end: string | null) =>
      mockUseAuth.mockReturnValue({
        user: { email: 'me@example.com', role: 'staff', is_dj_network: false, is_station_office_network: false, profile: { id: 1, name: 'Me', phone: '555-0000', dj_name: null, is_sublist_dj: false, loa_start, loa_end } },
        loading: false,
        error: null,
        refetchUser: vi.fn(),
      });

    it('replaces the Claim buttons with an explanation during a leave covering the show', async () => {
      onLeave('2024-12-01', '2025-01-15');
      vi.mocked(showsAPI.get).mockResolvedValue(mockShow);

      render(<BrowserRouter><ShowDetail /></BrowserRouter>);

      expect(
        await screen.findByText(
          "You're on leave of absence Dec 1, 2024 – Jan 15, 2025, so you can't claim passes for this show."
        )
      ).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /^claim$/i })).not.toBeInTheDocument();
    });

    it('leaves Claim available when the leave ends before the show', async () => {
      onLeave(null, '2024-12-30');
      vi.mocked(showsAPI.get).mockResolvedValue(mockShow);

      render(<BrowserRouter><ShowDetail /></BrowserRouter>);

      expect(await screen.findByRole('button', { name: /^claim$/i })).not.toBeDisabled();
      expect(screen.queryByText(/on leave of absence/i)).not.toBeInTheDocument();
    });
  });

  describe('21+ shows and birth years', () => {
    const loginAsSomeoneElse = () =>
      mockUseAuth.mockReturnValue({
        user: { email: 'someone-else@example.com', role: 'staff', is_dj_network: false, is_station_office_network: false, profile: { id: 1, name: 'Someone Else', phone: '555-0000', dj_name: null, is_sublist_dj: false } },
        loading: false,
        error: null,
        refetchUser: vi.fn(),
      });

    it('replaces the Claim buttons with why for staff who must be under 21', async () => {
      loginAsSomeoneElse();
      vi.mocked(showsAPI.getMyAgeChecks).mockResolvedValue({ 1: 'under_21' });
      vi.mocked(showsAPI.get).mockResolvedValue(mockShow);

      await renderAndSettle(<BrowserRouter><ShowDetail /></BrowserRouter>);

      expect(
        await screen.findByText(
          "This show is 21+. Going by the birth year in your staff record, you'll be under 21 on Dec 31, 2024, so you can't get a pass for it."
        )
      ).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /^claim$/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /claim with \+1 guest/i })).not.toBeInTheDocument();
    });

    it('warns staff who might be under 21 but lets them claim', async () => {
      loginAsSomeoneElse();
      vi.mocked(showsAPI.getMyAgeChecks).mockResolvedValue({ 1: 'maybe_under_21' });
      vi.mocked(showsAPI.get).mockResolvedValue(mockShow);

      await renderAndSettle(<BrowserRouter><ShowDetail /></BrowserRouter>);

      expect(await screen.findByRole('alert')).toHaveTextContent(
        "you might be under 21 on Dec 31, 2024. Make sure you'll be 21 or over that day"
      );
      expect(screen.getByRole('button', { name: /^claim$/i })).not.toBeDisabled();
    });

    it('asks staff under 21 who already have a pass to release it', async () => {
      loginAsClaimer();
      vi.mocked(showsAPI.getMyAgeChecks).mockResolvedValue({ 1: 'under_21' });
      vi.mocked(showsAPI.get).mockResolvedValue(mockShow);

      await renderAndSettle(<BrowserRouter><ShowDetail /></BrowserRouter>);

      expect(await screen.findByRole('alert')).toHaveTextContent(
        "you'll be under 21 on Dec 31, 2024, so you can't get a pass for it. Please release yours."
      );
      expect(screen.getByRole('button', { name: /release/i })).toBeInTheDocument();
    });

    it("says nothing when the show isn't one they're too young for", async () => {
      loginAsSomeoneElse();
      vi.mocked(showsAPI.getMyAgeChecks).mockResolvedValue({ 99: 'under_21' });
      vi.mocked(showsAPI.get).mockResolvedValue(mockShow);

      await renderAndSettle(<BrowserRouter><ShowDetail /></BrowserRouter>);

      expect(await screen.findByRole('button', { name: /^claim$/i })).not.toBeDisabled();
      expect(screen.queryByText(/under 21/)).not.toBeInTheDocument();
    });

    it("reminds staff that a 21+ show's +1 guest must be 21+ too", async () => {
      loginAsSomeoneElse();
      vi.mocked(showsAPI.get).mockResolvedValue({
        ...mockShow,
        passes: [availablePass, { ...availablePass, id: 3 }],
        available_staff_count: 2,
      });

      await renderAndSettle(<BrowserRouter><ShowDetail /></BrowserRouter>);
      fireEvent.click((await screen.findAllByRole('button', { name: /claim with \+1 guest/i }))[0]);

      expect(
        await screen.findByText('This show is 21+, so your guest must be 21 or over too.')
      ).toBeInTheDocument();
    });
  });

  describe('New (not yet Active) staff', () => {
    const newUser: UserResponse = {
      email: 'trainee@example.com',
      role: 'staff',
      is_dj_network: false,
      is_station_office_network: false,
      can_claim_staff_passes: false,
      profile: { id: 1, name: 'Trainee', phone: '555-0000', dj_name: null, is_sublist_dj: false },
    };

    beforeEach(() => {
      mockUseAuth.mockReturnValue({ user: newUser, loading: false, error: null, refetchUser: vi.fn() });
    });

    it('shows the Claim buttons disabled, with why', async () => {
      vi.mocked(showsAPI.get).mockResolvedValue({
        ...mockShow,
        passes: [availablePass, { ...availablePass, id: 3 }],
        available_staff_count: 2,
      });

      render(<BrowserRouter><ShowDetail /></BrowserRouter>);

      expect(
        await screen.findByText('Staff passes open to you once your status is Active.')
      ).toBeInTheDocument();
      for (const button of screen.getAllByRole('button', { name: /^claim$/i })) {
        expect(button).toBeDisabled();
      }
      for (const button of screen.getAllByRole('button', { name: /claim with \+1 guest/i })) {
        expect(button).toBeDisabled();
      }
    });

    it('shows the Join Alternate List button disabled', async () => {
      vi.mocked(showsAPI.get).mockResolvedValue({
        ...mockShow,
        passes: [claimedPass, { ...claimedPass, id: 3, staff_name: 'Ken', staff_email: 'ken@example.com' }],
        available_staff_count: 0,
      });
      vi.mocked(alternatesAPI.getQueue).mockResolvedValue({
        queue_open: true,
        entries: [],
        my_entry_id: null,
        next_candidate_staff_id: null,
        next_candidate_name: null,
        my_outcome_pending: false,
      });

      render(<BrowserRouter><ShowDetail /></BrowserRouter>);

      expect(await screen.findByRole('button', { name: /join alternate list/i })).toBeDisabled();
    });
  });

  describe('Release Pass', () => {
    it('should call releaseClaim API with pass ID', async () => {
      loginAsClaimer();
      vi.mocked(showsAPI.get).mockResolvedValue(mockShow);
      vi.mocked(passesAPI.releaseClaim).mockResolvedValue({
        ...claimedPass,
        status: 'available',
        staff_name: null,
      });

      render(
        <BrowserRouter>
          <ShowDetail />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /^release$/i })).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /^release$/i }));

      await waitFor(() => {
        expect(passesAPI.releaseClaim).toHaveBeenCalledWith(2);
      });
    });

    it('should show success message after release', async () => {
      loginAsClaimer();
      vi.mocked(showsAPI.get).mockResolvedValue(mockShow);
      vi.mocked(passesAPI.releaseClaim).mockResolvedValue({
        ...claimedPass,
        status: 'available',
      });

      render(
        <BrowserRouter>
          <ShowDetail />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /^release$/i })).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /^release$/i }));

      await waitFor(() => {
        expect(screen.getByText('Pass released.')).toBeInTheDocument();
      });
    });
  });

  describe('Alternate list', () => {
    const meUser: UserResponse = {
      email: 'me@example.com',
      role: 'staff',
      is_dj_network: false,
      is_station_office_network: false,
      profile: { id: 1, name: 'Me', phone: '555-0000', dj_name: null, is_sublist_dj: false },
    };
    const fullShow: ShowResponse = {
      ...mockShow,
      passes: [claimedPass, { ...claimedPass, id: 3, staff_name: 'Ken', staff_email: 'ken@example.com' }],
      available_staff_count: 0,
    };
    const entry = (overrides: Partial<AlternateEntry>): AlternateEntry => ({
      id: 10,
      show_id: 1,
      staff_id: 20,
      staff_name: 'Alex Alt',
      staff_phone: null,
      staff_email: null,
      position: 1,
      has_guest: false,
      guest_name: null,
      guest_fallback: 'attend_alone' as const,
      source: 'joined',
      priority_at: '2024-01-11T10:00:00Z',
      ...overrides,
    });
    const queue = (overrides: Partial<AlternateQueue>): AlternateQueue => ({
      queue_open: true,
      entries: [],
      my_entry_id: null,
      next_candidate_staff_id: null,
      next_candidate_name: null,
      my_outcome_pending: false,
      ...overrides,
    });

    beforeEach(() => {
      mockUseAuth.mockReturnValue({ user: meUser, loading: false, error: null, refetchUser: vi.fn() });
    });

    it('tells an alternate an outcome email is coming while it is held', async () => {
      vi.mocked(showsAPI.get).mockResolvedValue({
        ...fullShow,
        status: 'closed',
        close_notifications_pending: true,
      });
      vi.mocked(alternatesAPI.getQueue).mockResolvedValue(
        queue({ queue_open: false, my_outcome_pending: true })
      );

      render(<BrowserRouter><ShowDetail /></BrowserRouter>);

      expect(
        await screen.findByText("The show has closed. You'll get an email with the outcome.")
      ).toBeInTheDocument();
    });

    it('tells only the +1 host that an email is coming while it is held', async () => {
      vi.mocked(showsAPI.get).mockResolvedValue({
        ...mockShow,
        status: 'closed',
        close_notifications_pending: true,
        passes: [
          { ...claimedPass, has_guest: true, staff_email: 'me@example.com' },
          { ...claimedPass, id: 3, has_guest: true, staff_name: 'Ken', staff_email: 'ken@example.com' },
        ],
      });
      vi.mocked(alternatesAPI.getQueue).mockResolvedValue(queue({ queue_open: false }));

      render(<BrowserRouter><ShowDetail /></BrowserRouter>);

      expect(await screen.findByText("not confirmed yet, you'll get an email")).toBeInTheDocument();
      expect(screen.getByText('not confirmed yet')).toBeInTheDocument();
      expect(screen.queryByText('not confirmed until show closes')).not.toBeInTheDocument();
      await waitFor(() => expect(alternatesAPI.getQueue).toHaveBeenCalled());
    });

    it('hides the join control while passes are still available', async () => {
      vi.mocked(showsAPI.get).mockResolvedValue(mockShow);
      vi.mocked(alternatesAPI.getQueue).mockResolvedValue(queue({ queue_open: false }));

      render(<BrowserRouter><ShowDetail /></BrowserRouter>);

      await waitFor(() => expect(alternatesAPI.getQueue).toHaveBeenCalledWith(1));
      expect(screen.queryByRole('button', { name: /join alternate list/i })).not.toBeInTheDocument();
    });

    it('lets a user join once every pass is taken', async () => {
      vi.mocked(showsAPI.get).mockResolvedValue(fullShow);
      vi.mocked(alternatesAPI.getQueue).mockResolvedValue(
        queue({ entries: [entry({})] })
      );
      vi.mocked(alternatesAPI.join).mockResolvedValue(entry({ id: 11, position: 2, staff_name: 'Me' }));

      render(<BrowserRouter><ShowDetail /></BrowserRouter>);

      await waitFor(() => {
        expect(screen.getByText(/1 person is already on the alternate list/i)).toBeInTheDocument();
      });
      fireEvent.click(screen.getByRole('button', { name: /join alternate list/i }));
      fireEvent.click(screen.getByLabelText(/a pass for me and a guest/i));
      fireEvent.click(screen.getByRole('button', { name: /join alternate list/i }));

      await waitFor(() => {
        expect(alternatesAPI.join).toHaveBeenCalledWith(1, {
          has_guest: true,
          guest_name: null,
          guest_fallback: 'attend_alone' as const,
        });
      });
      expect(await screen.findByText(/you're alternate #2/i)).toBeInTheDocument();
    });

    it('renders alternates after a divider with position labels', async () => {
      vi.mocked(showsAPI.get).mockResolvedValue(fullShow);
      vi.mocked(alternatesAPI.getQueue).mockResolvedValue(
        queue({
          entries: [
            entry({}),
            entry({ id: 11, staff_id: 21, staff_name: 'Me', position: 2, has_guest: true, guest_name: 'Pal' }),
          ],
          my_entry_id: 11,
        })
      );

      render(<BrowserRouter><ShowDetail /></BrowserRouter>);

      expect(await screen.findByRole('separator')).toHaveTextContent('Alternates (2)');
      expect(screen.getByText('Alternate #1')).toBeInTheDocument();
      expect(screen.getByText(/1 person is ahead of you/i)).toBeInTheDocument();
      expect(screen.getByText(/\+1 guest requested: Pal/)).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /join alternate list/i })).not.toBeInTheDocument();

      vi.mocked(alternatesAPI.leave).mockResolvedValue(undefined);
      fireEvent.click(screen.getByRole('button', { name: /leave list/i }));
      await waitFor(() => expect(alternatesAPI.leave).toHaveBeenCalledWith(1));
    });

    describe('+1 guests on the alternate list', () => {
      const myPass = { ...claimedPass, staff_email: 'me@example.com', staff_name: 'Me' };
      const showPage = () => renderAndSettle(<BrowserRouter><ShowDetail /></BrowserRouter>);

      it('offers all four options in two groups with shared tradeoffs when a spare pass is free', async () => {
        vi.mocked(showsAPI.get).mockResolvedValue({
          ...fullShow,
          passes: [availablePass, { ...availablePass, id: 3 }],
        });
        vi.mocked(alternatesAPI.getQueue).mockResolvedValue(queue({ queue_open: false }));
        await showPage();

        fireEvent.click(screen.getAllByRole('button', { name: /claim with \+1 guest/i })[0]);

        expect(screen.getAllByRole('radio')).toHaveLength(4);
        expect(screen.getByRole('radio', { name: /still attend without them/i })).toBeChecked();
        expect(screen.getByRole('radio', { name: /release my pass too/i })).toBeInTheDocument();
        expect(screen.getByRole('radio', { name: /and i'll attend either way/i })).toBeInTheDocument();
        expect(screen.getByRole('radio', { name: /but release my pass/i })).toBeInTheDocument();
        expect(screen.getAllByText(/^Pro:/)).toHaveLength(2);
        expect(screen.getAllByText(/^Con:/)).toHaveLength(2);
        for (const name of [/still attend without them/i, /release my pass too/i]) {
          expect(screen.getByRole('radio', { name })).toHaveAccessibleDescription(/know immediately/i);
        }
        for (const name of [/and i'll attend either way/i, /but release my pass/i]) {
          expect(screen.getByRole('radio', { name })).toHaveAccessibleDescription(/until the show closes/i);
        }
      });

      it('offers only the waiting options when no spare pass is free', async () => {
        vi.mocked(showsAPI.get).mockResolvedValue({ ...fullShow, passes: [availablePass] });
        vi.mocked(alternatesAPI.getQueue).mockResolvedValue(queue({ queue_open: false }));
        vi.mocked(passesAPI.claim).mockResolvedValue({
          ...availablePass,
          status: 'claimed',
          guest_waiting: true,
        });
        await showPage();

        fireEvent.click(screen.getByRole('button', { name: /claim with \+1 guest/i }));

        expect(screen.getAllByRole('radio')).toHaveLength(2);
        expect(screen.getAllByText(/^Pro:/)).toHaveLength(1);
        expect(screen.getByText(/no pass free for your guest right now/i)).toBeInTheDocument();
        expect(screen.getByRole('radio', { name: /and i'll attend either way/i })).toBeChecked();

        fireEvent.click(screen.getByRole('radio', { name: /but release my pass/i }));
        fireEvent.click(screen.getByRole('button', { name: /^claim with \+1$/i }));

        expect(await screen.findByText(/your guest is on the alternate list/i)).toBeInTheDocument();
        expect(passesAPI.claim).toHaveBeenCalledWith(availablePass.id, {
          has_guest: true,
          guest_name: null,
          guest_fallback: 'wait_then_release',
        });
      });

      it('lists waiting guests below the staff alternates', async () => {
        vi.mocked(showsAPI.get).mockResolvedValue({ ...fullShow, passes: [claimedPass] });
        vi.mocked(alternatesAPI.getQueue).mockResolvedValue(
          queue({
            entries: [entry({})],
            waiting_guests: [
              {
                pass_id: 2,
                position: 1,
                guest_name: 'Sam',
                host_staff_id: 5,
                host_name: 'Alex',
                is_mine: false,
              },
            ],
          })
        );
        await showPage();

        expect(await screen.findByText('Guests waiting for a pass')).toBeInTheDocument();
        expect(screen.getByText('Guest #1')).toBeInTheDocument();
        expect(screen.getByText('Sam (guest of Alex)')).toBeInTheDocument();
        expect(screen.getByText('Alternate #1')).toBeInTheDocument();
      });

      it('shows the host their waiting guest and removes them', async () => {
        const waiting = {
          ...myPass,
          guest_waiting: true,
          guest_position: 2,
          guest_name: 'Sam',
          guest_fallback: 'wait' as const,
        };
        vi.mocked(showsAPI.get).mockResolvedValue({ ...fullShow, passes: [waiting] });
        vi.mocked(alternatesAPI.getQueue).mockResolvedValue(queue({ queue_open: false }));
        vi.mocked(passesAPI.removeGuest).mockResolvedValue(myPass);
        await showPage();

        expect(screen.getByText(/\+1 guest on the alternate list: Sam \(guest #2\)/)).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: /remove my guest/i }));
        expect(screen.getByText(/you'll keep your own pass/i)).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: /remove my guest/i }));

        expect(await screen.findByText('Your guest has been removed.')).toBeInTheDocument();
        expect(passesAPI.removeGuest).toHaveBeenCalledWith(waiting.id);
      });

      it('adds a guest to a pass claimed without one', async () => {
        vi.mocked(showsAPI.get).mockResolvedValue({ ...fullShow, passes: [myPass] });
        vi.mocked(alternatesAPI.getQueue).mockResolvedValue(queue({ queue_open: false }));
        vi.mocked(passesAPI.addGuest).mockResolvedValue({ ...myPass, guest_waiting: true });
        await showPage();

        fireEvent.click(screen.getByRole('button', { name: /add a guest/i }));
        expect(screen.getAllByRole('radio')).toHaveLength(2);
        fireEvent.click(screen.getByRole('button', { name: /^add guest$/i }));

        expect(await screen.findByText('Your guest has been added.')).toBeInTheDocument();
        expect(passesAPI.addGuest).toHaveBeenCalledWith(myPass.id, {
          guest_name: null,
          guest_fallback: 'wait',
        });
      });

      it('corrects a guest name', async () => {
        const seated = { ...myPass, has_guest: true, guest_name: 'Sma' };
        vi.mocked(showsAPI.get).mockResolvedValue({
          ...fullShow,
          guest_list_requirements: { ...fullShow.guest_list_requirements, staff_guest_requires_name: true },
          passes: [seated],
        });
        vi.mocked(alternatesAPI.getQueue).mockResolvedValue(queue({ queue_open: false }));
        vi.mocked(passesAPI.updateGuestName).mockResolvedValue({ ...seated, guest_name: 'Sam' });
        await showPage();

        fireEvent.click(screen.getByRole('button', { name: /fix guest name/i }));
        fireEvent.change(screen.getByLabelText(/guest name/i), { target: { value: 'Sam' } });
        fireEvent.click(screen.getByRole('button', { name: /save name/i }));

        expect(await screen.findByText("Your guest's name has been updated.")).toBeInTheDocument();
        expect(passesAPI.updateGuestName).toHaveBeenCalledWith(seated.id, 'Sam');
      });

      it("doesn't offer to fix the guest name when the venue doesn't need one", async () => {
        vi.mocked(showsAPI.get).mockResolvedValue({
          ...fullShow,
          passes: [{ ...myPass, has_guest: true, guest_name: null }],
        });
        vi.mocked(alternatesAPI.getQueue).mockResolvedValue(queue({ queue_open: false }));
        await showPage();

        expect(screen.getByRole('button', { name: /remove my guest/i })).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /fix guest name/i })).not.toBeInTheDocument();
      });

      it('hides a waiting guest\'s outcome while the close emails are held', async () => {
        vi.mocked(showsAPI.get).mockResolvedValue({
          ...fullShow,
          status: 'closed' as const,
          close_notifications_pending: true,
          passes: [{ ...myPass, guest_waiting: true, guest_position: 1, guest_name: 'Sam' }],
        });
        vi.mocked(alternatesAPI.getQueue).mockResolvedValue(queue({ queue_open: false }));
        await showPage();

        expect(screen.getByText(/not confirmed yet, you'll get an email/i)).toBeInTheDocument();
        expect(screen.queryByText(/didn't get a pass/i)).not.toBeInTheDocument();
        expect(screen.queryByText(/guest #1/i)).not.toBeInTheDocument();
      });

      it('says a waiting guest missed out once the show has closed', async () => {
        vi.mocked(showsAPI.get).mockResolvedValue({
          ...fullShow,
          status: 'closed' as const,
          close_notifications_pending: false,
          passes: [{ ...myPass, guest_waiting: true, guest_position: 1, guest_name: 'Sam' }],
        });
        vi.mocked(alternatesAPI.getQueue).mockResolvedValue(queue({ queue_open: false }));
        await showPage();

        expect(screen.getByText(/\+1 guest didn't get a pass: Sam/)).toBeInTheDocument();
      });

      it('says a seated guest is confirmed once the show has closed', async () => {
        vi.mocked(showsAPI.get).mockResolvedValue({
          ...fullShow,
          status: 'closed' as const,
          close_notifications_pending: false,
          passes: [{ ...myPass, has_guest: true, guest_name: 'Sam' }],
        });
        vi.mocked(alternatesAPI.getQueue).mockResolvedValue(queue({ queue_open: false }));
        await showPage();

        expect(screen.getByText('confirmed')).toBeInTheDocument();
        expect(screen.queryByText(/until show closes/i)).not.toBeInTheDocument();
      });

      it('hides the guest controls once the show closes', async () => {
        vi.mocked(showsAPI.get).mockResolvedValue({
          ...fullShow,
          status: 'closed' as const,
          passes: [{ ...myPass, has_guest: true, guest_name: 'Sam' }],
        });
        vi.mocked(alternatesAPI.getQueue).mockResolvedValue(queue({ queue_open: false }));
        await showPage();

        expect(screen.queryByRole('button', { name: /remove my guest/i })).not.toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /fix guest name/i })).not.toBeInTheDocument();
      });
    });

    it('warns who will get the pass before releasing', async () => {
      const myPass = { ...claimedPass, staff_email: 'me@example.com', staff_name: 'Me' };
      vi.mocked(showsAPI.get).mockResolvedValue({ ...fullShow, passes: [myPass] });
      vi.mocked(alternatesAPI.getQueue).mockResolvedValue(
        queue({ entries: [entry({})], next_candidate_staff_id: 20, next_candidate_name: 'Alex Alt' })
      );
      vi.mocked(passesAPI.releaseClaim).mockResolvedValue({ ...myPass, staff_name: 'Alex Alt' });

      render(<BrowserRouter><ShowDetail /></BrowserRouter>);

      await waitFor(() => expect(alternatesAPI.getQueue).toHaveBeenCalled());
      await screen.findByText('Alternate #1');
      fireEvent.click(screen.getByRole('button', { name: /^release$/i }));

      expect(
        screen.getByText((_, el) =>
          el?.tagName === 'P' &&
          /your pass will go to alex alt; you can rejoin at the back of the line/i.test(el.textContent ?? '')
        )
      ).toBeInTheDocument();
      expect(passesAPI.releaseClaim).not.toHaveBeenCalled();

      fireEvent.click(screen.getByRole('button', { name: /release pass/i }));
      await waitFor(() => expect(passesAPI.releaseClaim).toHaveBeenCalledWith(2));
    });
  });

  describe('Talk & Info Show staff members', () => {
    it('lets a staff member who isn’t a DJ reserve a pass pair for their show', async () => {
      mockUseAuth.mockReturnValue({
        user: { email: 'news@example.com', role: 'staff', is_dj_network: false, is_station_office_network: false, profile: { id: 9, name: 'Nia News', phone: '', dj_name: null, is_sublist_dj: false } },
        loading: false,
        error: null,
        refetchUser: vi.fn(),
      } as unknown as ReturnType<typeof mockUseAuth>);
      vi.mocked(passesAPI.getMyPreassignIdentities).mockResolvedValue([
        {
          name: 'Morning Report', kind: 'talk', persona_id: null, specialty_show_id: 7,
          dates: [], talk_show_dates: {},
        },
      ]);
      vi.mocked(showsAPI.get).mockResolvedValue({
        ...mockShow,
        passes: [{ ...availablePass, id: 3, pass_type: 'pair' }],
      });

      await renderAndSettle(<BrowserRouter><ShowDetail /></BrowserRouter>);

      fireEvent.click(await screen.findByRole('button', { name: 'Reserve for On-Air Giveaway' }));
      expect(await screen.findByDisplayValue('Morning Report (Talk & Info Show)')).toBeInTheDocument();
      expect(await screen.findByText(/No scheduled on-air dates found/)).toBeInTheDocument();
    });
  });

  describe('Reserving as one of your personas', () => {
    const loginAsDj = () =>
      mockUseAuth.mockReturnValue({
        user: {
          email: 'wolf@example.com', role: 'staff', is_dj_network: false, is_station_office_network: false,
          profile: { id: 4, name: 'Wolf', phone: '', dj_name: 'DJ Wolfman, Wolfie', spinitron_ids: [11, 12], is_sublist_dj: true },
        },
        loading: false,
        error: null,
        refetchUser: vi.fn(),
      } as unknown as ReturnType<typeof mockUseAuth>);

    const identities: MyIdentity[] = [
      { name: 'DJ Wolfman', kind: 'persona', persona_id: 11, specialty_show_id: null, dates: ['2099-12-01'], talk_show_dates: {} },
      { name: 'Wolfie', kind: 'persona', persona_id: 12, specialty_show_id: null, dates: ['2099-12-08'], talk_show_dates: { '2099-12-09': 'Morning Report' } },
    ];

    const openForm = async () => {
      vi.mocked(showsAPI.get).mockResolvedValue({
        ...mockShow,
        passes: [{ ...availablePass, id: 3, pass_type: 'pair' }],
      });
      await renderAndSettle(<BrowserRouter><ShowDetail /></BrowserRouter>);
      fireEvent.click(await screen.findByRole('button', { name: 'Reserve for On-Air Giveaway' }));
    };

    it('picks the persona on the schedule for the chosen date', async () => {
      loginAsDj();
      vi.mocked(passesAPI.getMyPreassignIdentities).mockResolvedValue(identities);
      vi.mocked(passesAPI.selfPreassign).mockResolvedValue({
        ...availablePass, id: 3, pass_type: 'pair', preassigned_dj: 'Wolfie', preassigned_persona_id: 12,
        preassigned_date: '2099-12-08',
      });

      await openForm();
      expect(await screen.findByDisplayValue('DJ Wolfman (my DJ name)')).toBeInTheDocument();
      fireEvent.change(screen.getByPlaceholderText('MM/DD/YYYY'), { target: { value: '12/08/2099' } });

      expect(await screen.findByDisplayValue('Wolfie (my DJ name)')).toBeInTheDocument();
      fireEvent.click(screen.getByRole('button', { name: 'Save' }));
      await waitFor(() =>
        expect(passesAPI.selfPreassign).toHaveBeenCalledWith(3, {
          assignment_date: '2099-12-08',
          persona_id: 12,
        }),
      );
      expect(await screen.findByText('Pass pre-assigned successfully!')).toBeInTheDocument();
    });

    it('warns when the chosen persona hosts a Talk & Info Show that day', async () => {
      loginAsDj();
      vi.mocked(passesAPI.getMyPreassignIdentities).mockResolvedValue(identities);

      await openForm();
      fireEvent.change(await screen.findByLabelText('Reserve for:'), { target: { value: 'p:12' } });
      fireEvent.change(screen.getByPlaceholderText('MM/DD/YYYY'), { target: { value: '12/09/2099' } });

      expect(
        await screen.findByText(/You host Morning Report \(Talk & Info Show\)/),
      ).toBeInTheDocument();
    });

    it("shows a pass promotions pre-assigned to one of your personas as yours", async () => {
      loginAsDj();
      vi.mocked(passesAPI.getMyPreassignIdentities).mockResolvedValue(identities);
      vi.mocked(showsAPI.get).mockResolvedValue({
        ...mockShow,
        passes: [{
          ...availablePass, id: 3, pass_type: 'pair', preassigned_dj: 'Wolfie',
          preassigned_persona_id: 12, preassigned_date: '2099-12-08',
        }],
      });

      await renderAndSettle(<BrowserRouter><ShowDetail /></BrowserRouter>);

      expect(await screen.findByRole('button', { name: 'Release Reservation' })).toBeInTheDocument();
      expect(screen.getByText('Tuesday, December 8, 2099')).toBeInTheDocument();
    });

    it("shows the DJ and date of a pass pair reserved by someone else", async () => {
      loginAsDj();
      vi.mocked(passesAPI.getMyPreassignIdentities).mockResolvedValue(identities);
      vi.mocked(showsAPI.get).mockResolvedValue({
        ...mockShow,
        passes: [{
          ...availablePass, id: 3, pass_type: 'pair', preassigned_dj: 'DJ Someone Else',
          preassigned_persona_id: 999, preassigned_date: '2099-12-08',
        }],
      });

      await renderAndSettle(<BrowserRouter><ShowDetail /></BrowserRouter>);

      expect(
        await screen.findByText('Pre-assigned to DJ Someone Else for Tuesday, December 8, 2099'),
      ).toBeInTheDocument();
    });
  });
});
