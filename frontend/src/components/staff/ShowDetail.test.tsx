import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import ShowDetail from './ShowDetail';
import { showsAPI, passesAPI, alternatesAPI } from '../../services/api';
import type { ShowResponse, PassResponse, UserResponse, AlternateEntry, AlternateQueue } from '../../types';

// Mock the API
vi.mock('../../services/api', () => ({
  showsAPI: {
    get: vi.fn(),
  },
  passesAPI: {
    claim: vi.fn(),
    releaseClaim: vi.fn(),
    removePreassignment: vi.fn(),
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
vi.mock('../../contexts/authHooks', () => ({
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

  const mockShow: ShowResponse = {
    id: 1,
    event_name: 'Test Concert',
    genre: ['Rock'],
    venue: { id: 1, name: 'Test Venue', address: '123 Main St', pass_call_instructions: null, win_frequency_days: null, default_wheelchair_accessible: null, default_age_restriction: null, default_num_pass_pairs: null, requires_phone_number: false, requires_email_address: false, staff_guest_requires_name: false, default_lottery_enabled: false, default_lottery_window_hours: 24, default_dj_preassign_prohibition_days: null, default_close_hours_before_show: null, has_logo: false, deleted: false, shows_have_external_promoter: false, owner_emails: [], contacts: [] },
    show_date: '2024-12-31',
    show_time: '20:00',
    show_start_date: null,
    on_air_description: null,
    caller_special_instructions: null,
    age_restriction: '21+',
    wheelchair_accessible: true,
    num_pass_pairs: 2,
    promotions_contacts: [],
    attempts: [],
    status: 'published',
    passes: [availablePass, claimedPass],
    available_pair_count: 0,
    available_staff_count: 1,
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
      on_kalx_live: false,
      kalx_live_appearances: [],
  };

  beforeEach(() => {
    vi.resetAllMocks();
    mockUseAuth.mockReturnValue({ user: null, loading: false, error: null, refetchUser: vi.fn() });
  });

  // Only the claimer sees Release on their own pass.
  const loginAsClaimer = () =>
    mockUseAuth.mockReturnValue({
      user: { email: 'jane@example.com', role: 'staff', is_dj_network: false, is_station_office_network: false, profile: { name: 'Jane Staff', phone: '555-999-0000', dj_name: null, is_sublist_dj: false } },
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
        user: { email: 'other@example.com', role: 'staff', is_dj_network: false, is_station_office_network: false, profile: { name: 'Other', phone: '555-0000', dj_name: null, is_sublist_dj: false } },
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
        user: { email: 'me@example.com', role: 'staff', is_dj_network: false, is_station_office_network: false, profile: { name: 'Me', phone: '555-0000', dj_name: null, is_sublist_dj: false } },
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

    it('leaves Claim enabled for a user with no existing pass on this show', async () => {
      mockUseAuth.mockReturnValue({
        user: { email: 'someone-else@example.com', role: 'staff', is_dj_network: false, is_station_office_network: false, profile: { name: 'Someone Else', phone: '555-0000', dj_name: null, is_sublist_dj: false } },
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
      profile: { name: 'Me', phone: '555-0000', dj_name: null, is_sublist_dj: false },
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
      position: 1,
      has_guest: false,
      guest_name: null,
      only_attend_with_guest: false,
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
      ...overrides,
    });

    beforeEach(() => {
      mockUseAuth.mockReturnValue({ user: meUser, loading: false, error: null, refetchUser: vi.fn() });
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
          only_attend_with_guest: false,
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
});
