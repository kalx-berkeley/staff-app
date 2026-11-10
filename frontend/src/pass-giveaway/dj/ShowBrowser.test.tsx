import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { renderAndSettle } from '../../test/render';
import { BrowserRouter } from 'react-router-dom';
import ShowBrowser from './ShowBrowser';
import { showsAPI, venuesAPI, passesAPI, autocompleteAPI } from '../api';
import type { ShowSummary, PassResponse } from '../types';
import { DJ_NAME_KEY } from '../components';

// Mock the API
vi.mock('../api', () => ({
  showsAPI: {
    list: vi.fn(),
    search: vi.fn(),
  },
  venuesAPI: {
    list: vi.fn(),
  },
  passesAPI: {
    getMyGiveaways: vi.fn(),
    clothespin: vi.fn(),
    removePreassignment: vi.fn(),
  },
  autocompleteAPI: {
    getDJNames: vi.fn(),
  },
  specialtyShowsAPI: {
    list: vi.fn().mockResolvedValue([]),
  },
  onAirAPI: {
    getCurrent: vi.fn().mockResolvedValue({
      current_dj_name: null,
      current_show_ends_at: null,
      next_dj_name: null,
    }),
  },
}));

describe('ShowBrowser', () => {
  const mockShows: ShowSummary[] = [
    {
      id: 1,
      event_name: 'Rock Concert',
      genre: ['Rock'],
      venue: { id: 1, name: 'The Venue', venue_type: 'music' },
      show_date: '2024-12-31',
      show_time: '20:00',
      show_start_date: null,
      caller_special_instructions: null,
      age_restriction: '21+',
      movie_rating: null,
      wheelchair_accessible: 'yes',
      num_pass_pairs: 3,
      staff_pass_adjustment: 0,
      num_staff_passes: 3,
      status: 'published',
      available_pair_count: 3,
      available_staff_count: 3,
      guest_hold_staff_count: 0,
      unassigned_pair_count: 3,
      clothespin_available: true,
      co_announce: false,
      published_at: null,
      bands: [],
      is_mine: false,
      in_feature_bin: false,
      feature_bin_releases: [],
      on_kalx_live: false,
      kalx_live_appearances: [],
    },
    {
      id: 2,
      event_name: 'Jazz Night',
      genre: ['Jazz'],
      venue: { id: 2, name: 'Jazz Club', venue_type: 'music' },
      show_date: '2025-01-15',
      show_time: '19:30',
      show_start_date: null,
      caller_special_instructions: 'VIP section available',
      age_restriction: '18+',
      movie_rating: null,
      wheelchair_accessible: 'no',
      num_pass_pairs: 2,
      staff_pass_adjustment: 0,
      num_staff_passes: 2,
      status: 'published',
      available_pair_count: 2,
      available_staff_count: 2,
      guest_hold_staff_count: 0,
      unassigned_pair_count: 2,
      clothespin_available: true,
      co_announce: false,
      published_at: null,
      bands: [],
      is_mine: false,
      in_feature_bin: false,
      feature_bin_releases: [],
      on_kalx_live: false,
      kalx_live_appearances: [],
    },
    {
      id: 3,
      event_name: 'Draft Show',
      genre: ['Pop'],
      venue: { id: 1, name: 'The Venue', venue_type: 'music' },
      show_date: '2025-02-01',
      show_time: '21:00',
      show_start_date: null,
      caller_special_instructions: null,
      age_restriction: 'all_ages',
      movie_rating: null,
      wheelchair_accessible: 'yes',
      num_pass_pairs: 1,
      staff_pass_adjustment: 0,
      num_staff_passes: 1,
      status: 'draft',
      available_pair_count: 1,
      available_staff_count: 1,
      guest_hold_staff_count: 0,
      unassigned_pair_count: 1,
      clothespin_available: true,
      co_announce: false,
      published_at: null,
      bands: [],
      is_mine: false,
      in_feature_bin: false,
      feature_bin_releases: [],
      on_kalx_live: false,
      kalx_live_appearances: [],
    },
    {
      id: 4,
      event_name: 'Closed Show',
      genre: ['Rock'],
      venue: { id: 1, name: 'The Venue', venue_type: 'music' },
      show_date: '2024-11-01',
      show_time: '20:00',
      show_start_date: null,
      caller_special_instructions: null,
      age_restriction: '21+',
      movie_rating: null,
      wheelchair_accessible: 'yes',
      num_pass_pairs: 2,
      staff_pass_adjustment: 0,
      num_staff_passes: 2,
      status: 'closed',
      available_pair_count: 0,
      available_staff_count: 0,
      guest_hold_staff_count: 0,
      unassigned_pair_count: 0,
      clothespin_available: true,
      co_announce: false,
      published_at: null,
      bands: [],
      is_mine: false,
      in_feature_bin: false,
      feature_bin_releases: [],
      on_kalx_live: false,
      kalx_live_appearances: [],
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(venuesAPI.list).mockResolvedValue([]);
    vi.mocked(autocompleteAPI.getDJNames).mockResolvedValue([]);
    vi.mocked(passesAPI.getMyGiveaways).mockResolvedValue([]);
    localStorage.clear();
  });

  describe('Show Filtering', () => {
    it('should only display published shows', async () => {
      vi.mocked(showsAPI.list).mockResolvedValue(mockShows);

      render(
        <BrowserRouter>
          <ShowBrowser />
        </BrowserRouter>
      );

      // Wait for the full render chain: loading → rawShows → allShows → filteredShows (via SearchBar)
      await waitFor(() => {
        expect(screen.getByText('Rock Concert')).toBeInTheDocument();
      });

      // Published shows should be visible
      expect(screen.getByText('Jazz Night')).toBeInTheDocument();

      // Draft and closed shows should not be visible
      expect(screen.queryByText('Draft Show')).not.toBeInTheDocument();
      expect(screen.queryByText('Closed Show')).not.toBeInTheDocument();
    });

    it('should display message when no shows are available', async () => {
      vi.mocked(showsAPI.list).mockResolvedValue([]);

      render(
        <BrowserRouter>
          <ShowBrowser />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('No shows available at this time.')).toBeInTheDocument();
      });
    });

    it('should display message when all shows are filtered out', async () => {
      const draftShows = mockShows.filter((show) => show.status === 'draft');
      vi.mocked(showsAPI.list).mockResolvedValue(draftShows);

      render(
        <BrowserRouter>
          <ShowBrowser />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('No shows available at this time.')).toBeInTheDocument();
      });
    });
  });

  describe('Show Information Display', () => {
    it('should display show details correctly', async () => {
      vi.mocked(showsAPI.list).mockResolvedValue([mockShows[0]]);

      render(
        <BrowserRouter>
          <ShowBrowser />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('Rock Concert')).toBeInTheDocument();
        expect(screen.getByText('Rock')).toBeInTheDocument();
        expect(screen.getByText('The Venue')).toBeInTheDocument();
        expect(screen.getByText('21+')).toBeInTheDocument();
        expect(screen.getByText('Yes')).toBeInTheDocument();
      });
    });

    it('should format date correctly', async () => {
      vi.mocked(showsAPI.list).mockResolvedValue([mockShows[0]]);

      render(
        <BrowserRouter>
          <ShowBrowser />
        </BrowserRouter>
      );

      await waitFor(() => {
        // Date should be formatted - check for "Dec" and "2024"
        expect(screen.getByText(/Dec.*2024/)).toBeInTheDocument();
      });
    });

    it('should format time correctly', async () => {
      vi.mocked(showsAPI.list).mockResolvedValue([mockShows[0]]);

      render(
        <BrowserRouter>
          <ShowBrowser />
        </BrowserRouter>
      );

      await waitFor(() => {
        // Time should be formatted as "8:00 PM"
        expect(screen.getByText('8:00 PM')).toBeInTheDocument();
      });
    });

    it('should display available pass pair count', async () => {
      vi.mocked(showsAPI.list).mockResolvedValue([mockShows[0]]);

      render(
        <BrowserRouter>
          <ShowBrowser />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('3')).toBeInTheDocument();
        expect(screen.getByText('Pass Pairs Available:')).toBeInTheDocument();
      });
    });

    it('should display wheelchair accessibility status', async () => {
      vi.mocked(showsAPI.list).mockResolvedValue([mockShows[0], mockShows[1]]);

      render(
        <BrowserRouter>
          <ShowBrowser />
        </BrowserRouter>
      );

      await waitFor(() => {
        const yesElements = screen.getAllByText('Yes');
        const noElements = screen.getAllByText('No');
        expect(yesElements.length).toBeGreaterThan(0);
        expect(noElements.length).toBeGreaterThan(0);
      });
    });

    it('should display link to show detail page', async () => {
      vi.mocked(showsAPI.list).mockResolvedValue([mockShows[0]]);

      render(
        <BrowserRouter>
          <ShowBrowser />
        </BrowserRouter>
      );

      await waitFor(() => {
        const link = screen.getByRole('link', { name: /give away passes/i });
        expect(link).toHaveAttribute('href', '/dj/shows/1');
      });
    });
  });

  describe('Loading and Error States', () => {
    it('should display loading message while fetching shows', async () => {
      vi.mocked(showsAPI.list).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(
        <BrowserRouter>
          <ShowBrowser />
        </BrowserRouter>
      );

      expect(screen.getByText('Loading shows...')).toBeInTheDocument();

      // Let the DJ name field's own mount-time lookups (autocomplete names,
      // on-air schedule) and the venue dropdown's fetch settle before the
      // test ends, so their state updates land inside act().
      await waitFor(() => expect(autocompleteAPI.getDJNames).toHaveBeenCalled());
    });

    it('should display error message when API call fails', async () => {
      vi.mocked(showsAPI.list).mockRejectedValue({
        detail: 'Failed to fetch shows',
      });

      render(
        <BrowserRouter>
          <ShowBrowser />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('Error: Failed to fetch shows')).toBeInTheDocument();
      });
    });

    it('should display generic error message when API error has no detail', async () => {
      vi.mocked(showsAPI.list).mockRejectedValue({
        detail: [{ loc: ['body'], msg: 'Invalid', type: 'error' }],
      });

      render(
        <BrowserRouter>
          <ShowBrowser />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('Error: Failed to load shows')).toBeInTheDocument();
      });
    });

    it('should provide retry button on error', async () => {
      vi.mocked(showsAPI.list).mockRejectedValueOnce({
        detail: 'Network error',
      });

      render(
        <BrowserRouter>
          <ShowBrowser />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('Error: Network error')).toBeInTheDocument();
      });

      const retryButton = screen.getByRole('button', { name: /retry/i });
      expect(retryButton).toBeInTheDocument();

      // Mock successful retry
      vi.mocked(showsAPI.list).mockResolvedValue([mockShows[0]]);
      fireEvent.click(retryButton);

      await waitFor(() => {
        expect(screen.getByText('Rock Concert')).toBeInTheDocument();
      });
    });
  });

  describe('Multiple Shows Display', () => {
    it('should display multiple published shows', async () => {
      const publishedShows = mockShows.filter((show) => show.status === 'published');
      vi.mocked(showsAPI.list).mockResolvedValue(publishedShows);

      render(
        <BrowserRouter>
          <ShowBrowser />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('Rock Concert')).toBeInTheDocument();
        expect(screen.getByText('Jazz Night')).toBeInTheDocument();
      });
    });

    it('should display correct pass counts for each show', async () => {
      const publishedShows = mockShows.filter((show) => show.status === 'published');
      vi.mocked(showsAPI.list).mockResolvedValue(publishedShows);

      render(
        <BrowserRouter>
          <ShowBrowser />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('3')).toBeInTheDocument(); // Rock Concert
        expect(screen.getByText('2')).toBeInTheDocument(); // Jazz Night
      });
    });
  });

  describe('Clothespin and Release Reservation', () => {
    const localToday = () => {
      const d = new Date();
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    };

    const reservedPass = (overrides: Partial<PassResponse> = {}): PassResponse => ({
      id: 20,
      show_id: 2,
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
      preassigned_dj: 'DJ Wolfman',
      preassigned_date: localToday(),
      preassigned_specialty_show_id: null,
      preassigned_specialty_show_name: null,
      show_event_name: 'Jazz Night',
      show_date: '2025-01-15',
      show_venue_name: 'Jazz Club',
      ...overrides,
    });

    // Rock Concert and Jazz Night allow Clothespin; Folk Fest doesn't.
    const clothespinShows: ShowSummary[] = [
      mockShows[0],
      mockShows[1],
      { ...mockShows[0], id: 5, event_name: 'Folk Fest', clothespin_available: false },
    ];

    const clothespinButton = (eventName: string) =>
      screen.queryByRole('button', { name: `Clothespin a pass pair for ${eventName}` });

    // The DJ's pre-assigned passes load 300 ms after the name is set, so wait
    // for the section to show them before checking anything that depends on them.
    const renderWithDj = async () => {
      localStorage.setItem(DJ_NAME_KEY, 'DJ Wolfman');
      await renderAndSettle(
        <BrowserRouter>
          <ShowBrowser />
        </BrowserRouter>
      );
      await screen.findByText('Your Pre-assigned Shows');
      await screen.findByText('Rock Concert');
    };

    beforeEach(() => {
      vi.mocked(showsAPI.list).mockResolvedValue(clothespinShows);
      vi.mocked(passesAPI.getMyGiveaways).mockResolvedValue([reservedPass()]);
    });

    it('shows Clothespin only where it is allowed and not already reserved for today', async () => {
      await renderWithDj();

      expect(clothespinButton('Rock Concert')).toBeInTheDocument();
      expect(clothespinButton('Rock Concert')).toHaveAttribute(
        'title',
        "Reserve one pass pair under your DJ name for today's on-air giveaway"
      );
      // Already reserved for this DJ for today.
      expect(clothespinButton('Jazz Night')).not.toBeInTheDocument();
      // The show's rules don't allow it, or no unclaimed pair is left.
      expect(clothespinButton('Folk Fest')).not.toBeInTheDocument();
      expect(passesAPI.getMyGiveaways).toHaveBeenCalledWith('DJ Wolfman');
    });

    it('still shows Clothespin when the DJ only has a reservation for another day', async () => {
      vi.mocked(passesAPI.getMyGiveaways).mockResolvedValue([
        reservedPass({ preassigned_date: '2099-01-01' }),
      ]);
      await renderWithDj();

      expect(clothespinButton('Jazz Night')).toBeInTheDocument();
    });

    it('hides Clothespin when no DJ name is set', async () => {
      await renderAndSettle(
        <BrowserRouter>
          <ShowBrowser />
        </BrowserRouter>
      );
      await screen.findByText('Rock Concert');

      expect(screen.queryAllByRole('button', { name: /^Clothespin/ })).toHaveLength(0);
      expect(passesAPI.getMyGiveaways).not.toHaveBeenCalled();
    });

    it('reserves a pair, confirms it and refreshes the page', async () => {
      const newPass = reservedPass({ id: 21, show_id: 1, show_event_name: 'Rock Concert' });
      vi.mocked(passesAPI.clothespin).mockResolvedValue(newPass);
      await renderWithDj();
      vi.mocked(passesAPI.getMyGiveaways).mockResolvedValue([reservedPass(), newPass]);

      fireEvent.click(clothespinButton('Rock Concert')!);

      expect(await screen.findByRole('status')).toHaveTextContent(
        'Reserved a pass pair for Rock Concert for DJ Wolfman today.'
      );
      expect(passesAPI.clothespin).toHaveBeenCalledWith(1, 'DJ Wolfman');
      await waitFor(() => expect(clothespinButton('Rock Concert')).not.toBeInTheDocument());
      expect(showsAPI.list).toHaveBeenCalledTimes(2);
      // The list refreshed in place, without the loading screen.
      expect(screen.queryByText('Loading shows...')).not.toBeInTheDocument();
    });

    it('shows the reason when Clothespin is refused', async () => {
      vi.mocked(passesAPI.clothespin).mockRejectedValue({
        detail: '‘DJ Wolfman’ isn\'t a known DJ or specialty show name',
      });
      await renderWithDj();

      fireEvent.click(clothespinButton('Rock Concert')!);

      expect(await screen.findByRole('alert')).toHaveTextContent(
        '‘DJ Wolfman’ isn\'t a known DJ or specialty show name'
      );
      expect(await screen.findByRole('button', { name: 'Clothespin a pass pair for Rock Concert' })).toBeEnabled();
    });

    it('releases a reservation after the DJ confirms', async () => {
      const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
      vi.mocked(passesAPI.removePreassignment).mockResolvedValue(
        reservedPass({ preassigned_dj: null, preassigned_date: null })
      );
      await renderWithDj();
      vi.mocked(passesAPI.getMyGiveaways).mockResolvedValue([]);

      fireEvent.click(screen.getByRole('button', { name: 'Release reservation for Jazz Night' }));

      expect(await screen.findByRole('status')).toHaveTextContent(
        'Released your pass pair for Jazz Night.'
      );
      expect(confirmSpy).toHaveBeenCalled();
      expect(passesAPI.removePreassignment).toHaveBeenCalledWith(20, 'DJ Wolfman');
      await waitFor(() =>
        expect(screen.queryByText('Your Pre-assigned Shows')).not.toBeInTheDocument()
      );
      confirmSpy.mockRestore();
    });

    it('keeps the reservation when the DJ cancels the confirmation', async () => {
      const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
      await renderWithDj();

      fireEvent.click(screen.getByRole('button', { name: 'Release reservation for Jazz Night' }));

      expect(passesAPI.removePreassignment).not.toHaveBeenCalled();
      expect(screen.getByText('Your Pre-assigned Shows')).toBeInTheDocument();
      confirmSpy.mockRestore();
    });

    it('shows both buttons in the list view too', async () => {
      localStorage.setItem('kalx_dj_view_mode', 'compact');
      await renderWithDj();

      const assignedRow = screen.getByRole('button', { name: 'Release reservation for Jazz Night' }).closest('tr')!;
      expect(within(assignedRow).getByRole('link', { name: 'Give Away Passes' })).toBeInTheDocument();
      const showRow = clothespinButton('Rock Concert')!.closest('tr')!;
      expect(within(showRow).getByRole('link', { name: 'Give Away' })).toBeInTheDocument();
    });

    describe('a show this DJ already gave a pair away for this shift', () => {
      const givenAway = (hoursAgo: number): PassResponse => ({
        ...reservedPass(),
        id: 30,
        show_id: 1,
        status: 'given_away',
        preassigned_dj: null,
        preassigned_date: null,
        given_away_by_dj: 'DJ Wolfman',
        given_away_at: new Date(Date.now() - hoursAgo * 60 * 60 * 1000).toISOString(),
      });

      const mainCard = (eventName: string) =>
        screen
          .getAllByText(eventName)
          .map((el) => el.closest('.show-card') as HTMLElement)
          .find((el) => el && !el.closest('.assigned-shows-section'))!;

      it('offers View Show instead of Give Away within the shift', async () => {
        vi.mocked(passesAPI.getMyGiveaways).mockResolvedValue([reservedPass(), givenAway(1)]);
        await renderWithDj();

        const rockCard = mainCard('Rock Concert');
        expect(within(rockCard).queryByRole('link', { name: 'Give Away Passes' })).not.toBeInTheDocument();
        expect(within(rockCard).getByRole('link', { name: 'View Show' })).toHaveAttribute('href', '/dj/shows/1');
        expect(rockCard).toHaveClass('show-card-dimmed');
        expect(rockCard.getAttribute('title')).toMatch(/already gave away a pass pair for this show this DJ shift/);
      });

      it('offers Give Away again once the shift is over', async () => {
        vi.mocked(passesAPI.getMyGiveaways).mockResolvedValue([reservedPass(), givenAway(5)]);
        await renderWithDj();

        const rockCard = mainCard('Rock Concert');
        expect(within(rockCard).getByRole('link', { name: 'Give Away Passes' })).toBeInTheDocument();
        expect(rockCard).not.toHaveClass('show-card-dimmed');
      });
    });

    describe('pairs pre-assigned to other DJs', () => {
      // Both available pairs are pre-assigned, so none is open to any DJ.
      const reservedShow: ShowSummary = {
        ...mockShows[0],
        id: 6,
        event_name: 'Sold Out Sounds',
        available_pair_count: 2,
        unassigned_pair_count: 0,
        clothespin_available: false,
      };

      // The show's card in the main list, not in "Your Pre-assigned Shows".
      const card = (eventName: string) =>
        screen
          .getAllByText(eventName)
          .map((el) => el.closest('.show-card') as HTMLElement)
          .find((el) => el && !el.closest('.assigned-shows-section'))!;

      beforeEach(() => {
        vi.mocked(showsAPI.list).mockResolvedValue([mockShows[0], mockShows[1], reservedShow]);
      });

      it('offers View Show instead of Give Away when every pair is pre-assigned to other DJs', async () => {
        await renderWithDj();
        await screen.findByText('Sold Out Sounds');

        const reservedCard = card('Sold Out Sounds');
        expect(within(reservedCard).queryByRole('link', { name: 'Give Away Passes' })).not.toBeInTheDocument();
        expect(within(reservedCard).getByRole('link', { name: 'View Show' })).toHaveAttribute('href', '/dj/shows/6');
        expect(within(reservedCard).getByText('2 pre-assigned to other DJs')).toBeInTheDocument();
        expect(reservedCard).toHaveClass('show-card-dimmed');
        expect(reservedCard).toHaveAttribute('title', 'Every pass pair left is pre-assigned to another DJ');

        const openCard = card('Rock Concert');
        expect(within(openCard).getByRole('link', { name: 'Give Away Passes' })).toBeInTheDocument();
        expect(openCard.querySelector('.pairs-reserved-note')).toBeNull();
      });

      it("counts the DJ's own pre-assigned pairs as theirs to give away", async () => {
        vi.mocked(passesAPI.getMyGiveaways).mockResolvedValue([
          reservedPass(),
          reservedPass({ id: 22, show_id: 6, show_event_name: 'Sold Out Sounds' }),
        ]);
        await renderWithDj();
        await waitFor(() => expect(screen.getAllByText('Sold Out Sounds')).toHaveLength(2));

        const reservedCard = card('Sold Out Sounds');
        expect(within(reservedCard).getByRole('link', { name: 'Give Away Passes' })).toBeInTheDocument();
        expect(within(reservedCard).getByText('1 pre-assigned to other DJs')).toBeInTheDocument();
        expect(reservedCard).not.toHaveClass('show-card-dimmed');
      });

      it('shows the pre-assigned pairs and a View link in the list view', async () => {
        localStorage.setItem('kalx_dj_view_mode', 'compact');
        await renderWithDj();
        await screen.findByText('Sold Out Sounds');

        const row = screen.getByText('Sold Out Sounds').closest('tr')!;
        expect(within(row).queryByRole('link', { name: 'Give Away' })).not.toBeInTheDocument();
        expect(within(row).getByRole('link', { name: 'View' })).toBeInTheDocument();
        expect(within(row).getByText('(2 pre-assigned)')).toHaveAttribute('title', '2 pre-assigned to other DJs');
      });
    });
  });
});
