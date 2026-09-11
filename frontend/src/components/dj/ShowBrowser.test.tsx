import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import ShowBrowser from './ShowBrowser';
import { showsAPI, venuesAPI, passesAPI, autocompleteAPI } from '../../services/api';
import type { ShowSummary } from '../../types';

// Mock the API
vi.mock('../../services/api', () => ({
  showsAPI: {
    list: vi.fn(),
    search: vi.fn(),
  },
  venuesAPI: {
    list: vi.fn(),
  },
  passesAPI: {
    getMyGiveaways: vi.fn(),
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
      venue: { id: 1, name: 'The Venue' },
      show_date: '2024-12-31',
      show_time: '20:00',
      show_start_date: null,
      caller_special_instructions: null,
      age_restriction: '21+',
      wheelchair_accessible: true,
      num_pass_pairs: 3,
      status: 'published',
      available_pair_count: 3,
      available_staff_count: 3,
      guest_hold_staff_count: 0,
      co_announce: false,
      published_at: null,
      bands: [],
      is_mine: false,
      in_feature_bin: false,
      feature_bin_releases: [],
    },
    {
      id: 2,
      event_name: 'Jazz Night',
      genre: ['Jazz'],
      venue: { id: 2, name: 'Jazz Club' },
      show_date: '2025-01-15',
      show_time: '19:30',
      show_start_date: null,
      caller_special_instructions: 'VIP section available',
      age_restriction: '18+',
      wheelchair_accessible: false,
      num_pass_pairs: 2,
      status: 'published',
      available_pair_count: 2,
      available_staff_count: 2,
      guest_hold_staff_count: 0,
      co_announce: false,
      published_at: null,
      bands: [],
      is_mine: false,
      in_feature_bin: false,
      feature_bin_releases: [],
    },
    {
      id: 3,
      event_name: 'Draft Show',
      genre: ['Pop'],
      venue: { id: 1, name: 'The Venue' },
      show_date: '2025-02-01',
      show_time: '21:00',
      show_start_date: null,
      caller_special_instructions: null,
      age_restriction: 'all_ages',
      wheelchair_accessible: true,
      num_pass_pairs: 1,
      status: 'draft',
      available_pair_count: 1,
      available_staff_count: 1,
      guest_hold_staff_count: 0,
      co_announce: false,
      published_at: null,
      bands: [],
      is_mine: false,
      in_feature_bin: false,
      feature_bin_releases: [],
    },
    {
      id: 4,
      event_name: 'Closed Show',
      genre: ['Rock'],
      venue: { id: 1, name: 'The Venue' },
      show_date: '2024-11-01',
      show_time: '20:00',
      show_start_date: null,
      caller_special_instructions: null,
      age_restriction: '21+',
      wheelchair_accessible: true,
      num_pass_pairs: 2,
      status: 'closed',
      available_pair_count: 0,
      available_staff_count: 0,
      guest_hold_staff_count: 0,
      co_announce: false,
      published_at: null,
      bands: [],
      is_mine: false,
      in_feature_bin: false,
      feature_bin_releases: [],
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
    it('should display loading message while fetching shows', () => {
      vi.mocked(showsAPI.list).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(
        <BrowserRouter>
          <ShowBrowser />
        </BrowserRouter>
      );

      expect(screen.getByText('Loading shows...')).toBeInTheDocument();
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
});
