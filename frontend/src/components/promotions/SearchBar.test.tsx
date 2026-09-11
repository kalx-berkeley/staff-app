import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import SearchBar from './SearchBar';
import { venuesAPI } from '../../services/api';
import type { VenueResponse, ShowSummary } from '../../types';

vi.mock('../../services/api', () => ({
  venuesAPI: {
    list: vi.fn(),
  },
}));

const makeVenue = (overrides: Partial<VenueResponse> = {}): VenueResponse => ({
  id: 1,
  name: 'Venue A',
  address: '123 Main St',
  pass_call_instructions: null,
  win_frequency_days: null,
  default_wheelchair_accessible: null,
  default_age_restriction: null,
  deleted: false,
  default_lottery_enabled: false,
  default_lottery_window_hours: 24,
  default_dj_preassign_prohibition_days: null,
  owner_emails: [],
  contacts: [],
  ...overrides,
} as VenueResponse);

const venueA = makeVenue({ id: 1, name: 'Venue A', address: '123 Main St' });
const venueB = makeVenue({ id: 2, name: 'Venue B', address: '456 Oak Ave' });

const mockVenues: VenueResponse[] = [venueA, venueB];

const makeShow = (overrides: Partial<ShowSummary> = {}): ShowSummary => ({
  id: 1,
  event_name: 'Rock Concert',
  genre: ['Rock'],
  venue: venueA,
  show_date: '2024-12-31',
  show_time: '20:00',
  show_start_date: null,
  caller_special_instructions: null,
  age_restriction: 'all_ages',
  wheelchair_accessible: true,
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
  ...overrides,
});

const rockShow = makeShow({ id: 1, event_name: 'Rock Concert', genre: ['Rock'], venue: venueA });
const jazzShow = makeShow({ id: 2, event_name: 'Jazz Night', genre: ['Jazz'], venue: venueB });

describe('SearchBar', () => {
  const mockOnSearch = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(venuesAPI.list).mockResolvedValue(mockVenues);
  });

  describe('Client-Side Filtering', () => {
    it('should call onSearch with all shows when no filters are applied', async () => {
      const shows = [rockShow, jazzShow];
      render(<SearchBar shows={shows} onSearch={mockOnSearch} />);

      await waitFor(() => {
        expect(mockOnSearch).toHaveBeenCalledWith(shows);
      });
    });

    it('should filter shows by freetext search', async () => {
      const shows = [rockShow, jazzShow];
      render(<SearchBar shows={shows} onSearch={mockOnSearch} />);

      await waitFor(() => expect(screen.getByLabelText(/search/i)).toBeInTheDocument());

      fireEvent.change(screen.getByLabelText(/search/i), { target: { value: 'Rock' } });

      await waitFor(() => {
        const lastCall = mockOnSearch.mock.calls[mockOnSearch.mock.calls.length - 1][0] as ShowSummary[];
        expect(lastCall).toHaveLength(1);
        expect(lastCall[0].event_name).toBe('Rock Concert');
      });
    });

    it('should filter shows by genre', async () => {
      const shows = [rockShow, jazzShow];
      render(<SearchBar shows={shows} onSearch={mockOnSearch} />);

      await waitFor(() => expect(screen.getByLabelText(/genre/i)).toBeInTheDocument());

      fireEvent.change(screen.getByLabelText(/genre/i), { target: { value: 'Jazz' } });

      await waitFor(() => {
        const lastCall = mockOnSearch.mock.calls[mockOnSearch.mock.calls.length - 1][0] as ShowSummary[];
        expect(lastCall).toHaveLength(1);
        expect(lastCall[0].event_name).toBe('Jazz Night');
      });
    });

    it('should filter shows by venue', async () => {
      const shows = [rockShow, jazzShow];
      render(<SearchBar shows={shows} onSearch={mockOnSearch} />);

      await waitFor(() => expect(screen.getByLabelText(/venue/i)).toBeInTheDocument());

      fireEvent.change(screen.getByLabelText(/venue/i), { target: { value: '2' } });

      await waitFor(() => {
        const lastCall = mockOnSearch.mock.calls[mockOnSearch.mock.calls.length - 1][0] as ShowSummary[];
        expect(lastCall).toHaveLength(1);
        expect(lastCall[0].event_name).toBe('Jazz Night');
      });
    });

    it('should return empty array when no shows match', async () => {
      const shows = [rockShow];
      render(<SearchBar shows={shows} onSearch={mockOnSearch} />);

      await waitFor(() => expect(screen.getByLabelText(/search/i)).toBeInTheDocument());

      fireEvent.change(screen.getByLabelText(/search/i), { target: { value: 'Nonexistent' } });

      await waitFor(() => {
        const lastCall = mockOnSearch.mock.calls[mockOnSearch.mock.calls.length - 1][0] as ShowSummary[];
        expect(lastCall).toHaveLength(0);
      });
    });
  });

  describe('Clear Filters', () => {
    it('should show clear button when filters are applied', async () => {
      render(<SearchBar shows={[rockShow]} onSearch={mockOnSearch} />);

      await waitFor(() => expect(screen.getByLabelText(/search/i)).toBeInTheDocument());

      fireEvent.change(screen.getByLabelText(/search/i), { target: { value: 'Rock' } });

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /clear/i })).toBeInTheDocument();
      });
    });

    it('should not show clear button when no filters are applied', async () => {
      render(<SearchBar shows={[rockShow]} onSearch={mockOnSearch} />);

      await waitFor(() => expect(screen.getByLabelText(/search/i)).toBeInTheDocument());

      expect(screen.queryByRole('button', { name: /clear/i })).not.toBeInTheDocument();
    });

    it('should clear all filters when clear button is clicked', async () => {
      const shows = [rockShow, jazzShow];
      render(<SearchBar shows={shows} onSearch={mockOnSearch} />);

      await waitFor(() => expect(screen.getByLabelText(/search/i)).toBeInTheDocument());

      fireEvent.change(screen.getByLabelText(/search/i), { target: { value: 'Rock' } });
      await waitFor(() => expect(screen.getByRole('button', { name: /clear/i })).toBeInTheDocument());

      fireEvent.click(screen.getByRole('button', { name: /clear/i }));

      await waitFor(() => {
        expect(screen.getByLabelText(/search/i)).toHaveValue('');
        const lastCall = mockOnSearch.mock.calls[mockOnSearch.mock.calls.length - 1][0] as ShowSummary[];
        expect(lastCall).toHaveLength(2);
      });
    });
  });

  describe('Venue Dropdown', () => {
    it('should populate venue dropdown from API', async () => {
      render(<SearchBar shows={[rockShow]} onSearch={mockOnSearch} />);

      await waitFor(() => {
        expect(screen.getByRole('option', { name: 'Venue A' })).toBeInTheDocument();
        expect(screen.getByRole('option', { name: 'Venue B' })).toBeInTheDocument();
      });
    });
  });

  describe('External Genre Prop', () => {
    it('should apply external genre filter when provided', async () => {
      const shows = [rockShow, jazzShow];
      render(<SearchBar shows={shows} onSearch={mockOnSearch} externalGenre="Jazz" />);

      await waitFor(() => {
        const lastCall = mockOnSearch.mock.calls[mockOnSearch.mock.calls.length - 1][0] as ShowSummary[];
        expect(lastCall).toHaveLength(1);
        expect(lastCall[0].genre).toEqual(['Jazz']);
      });
    });
  });
});
