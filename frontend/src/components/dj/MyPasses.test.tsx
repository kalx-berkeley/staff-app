import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import MyPasses from './MyPasses';
import { passesAPI, autocompleteAPI } from '../../services/api';
import type { PassResponse } from '../../types';

// Mock the API
vi.mock('../../services/api', () => ({
  passesAPI: {
    getMyGiveaways: vi.fn(),
  },
  autocompleteAPI: {
    getDJNames: vi.fn(),
  },
  onAirAPI: {
    getCurrent: vi.fn().mockResolvedValue({
      current_dj_name: null,
      current_show_ends_at: null,
      next_dj_name: null,
    }),
  },
}));

const DJ_NAME_KEY = 'kalx_dj_name';

describe('MyPasses', () => {
  const mockPasses: PassResponse[] = [
    {
      id: 1,
      show_id: 1,
      pass_type: 'pair',
      status: 'given_away',
      recipient_name: 'John Doe',
      recipient_phone: '555-123-4567',
      recipient_email: null,
      given_away_by_dj: 'DJ Mike',
      given_away_at: '2024-01-15T20:30:00',
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
    },
    {
      id: 2,
      show_id: 2,
      pass_type: 'pair',
      status: 'given_away',
      recipient_name: 'Jane Smith',
      recipient_phone: '555-567-8901',
      recipient_email: null,
      given_away_by_dj: 'DJ Mike',
      given_away_at: '2024-01-20T19:15:00',
      staff_id: null,
      staff_name: null,
      staff_phone: null,
      staff_email: null,
      claimed_at: null,
      has_guest: false,
      guest_name: null,
      only_attend_with_guest: false,
      guest_of_pass_id: null,
      preassigned_dj: 'DJ Mike',
      preassigned_date: '2024-01-20',
      preassigned_specialty_show_id: null,
      preassigned_specialty_show_name: null,
      show_event_name: null,
      show_date: null,
      show_venue_name: null,
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    // Never resolve — resolving promises here trigger state updates outside
    // act() in tests that don't await them.  Tests that need resolved values
    // override these mocks in their own body.
    vi.mocked(autocompleteAPI.getDJNames).mockReturnValue(new Promise(() => {}));
    vi.mocked(passesAPI.getMyGiveaways).mockReturnValue(new Promise(() => {}));
  });

  const renderWithDJName = (djName = 'DJ Mike') => {
    localStorage.setItem(DJ_NAME_KEY, djName);
    return render(<MyPasses />);
  };

  describe('MyPasses Display', () => {
    it('should display all passes given away by the DJ', async () => {
      vi.mocked(passesAPI.getMyGiveaways).mockResolvedValue(mockPasses);
      renderWithDJName();

      await waitFor(() => {
        const passCards = screen.getAllByText('Pass Pair');
        expect(passCards.length).toBe(2);
      });
    });

    it('should display winner information for each pass', async () => {
      vi.mocked(passesAPI.getMyGiveaways).mockResolvedValue(mockPasses);
      renderWithDJName();

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
        expect(screen.getByText('(555) 123-4567')).toBeInTheDocument();
        expect(screen.getByText('Jane Smith')).toBeInTheDocument();
        expect(screen.getByText('(555) 567-8901')).toBeInTheDocument();
      });
    });

    it('should display DJ name for each pass', async () => {
      vi.mocked(passesAPI.getMyGiveaways).mockResolvedValue(mockPasses);
      renderWithDJName();

      await waitFor(() => {
        const djMikeElements = screen.getAllByText('DJ Mike');
        expect(djMikeElements.length).toBeGreaterThanOrEqual(2);
      });
    });

    it('should display formatted date and time for each pass', async () => {
      vi.mocked(passesAPI.getMyGiveaways).mockResolvedValue(mockPasses);
      renderWithDJName();

      await waitFor(() => {
        expect(screen.getByText(/Jan 15, 2024/)).toBeInTheDocument();
        expect(screen.getByText(/Jan 20, 2024/)).toBeInTheDocument();
      });
    });

    it('should display pass status', async () => {
      vi.mocked(passesAPI.getMyGiveaways).mockResolvedValue(mockPasses);
      renderWithDJName();

      await waitFor(() => {
        const statusElements = screen.getAllByText('Given Away');
        expect(statusElements.length).toBe(2);
      });
    });

    it('should display pre-assignment information when present', async () => {
      vi.mocked(passesAPI.getMyGiveaways).mockResolvedValue([mockPasses[1]]);
      renderWithDJName();

      await waitFor(() => {
        expect(screen.getByText(/pre-assigned to:/i)).toBeInTheDocument();
        const djMikeElements = screen.getAllByText('DJ Mike');
        expect(djMikeElements.length).toBe(2);
      });
    });

    it('should not display pre-assignment when not present', async () => {
      vi.mocked(passesAPI.getMyGiveaways).mockResolvedValue([mockPasses[0]]);
      renderWithDJName();

      await waitFor(() => {
        expect(screen.queryByText(/pre-assigned to:/i)).not.toBeInTheDocument();
      });
    });

    it('should display message when no passes have been given away', async () => {
      vi.mocked(passesAPI.getMyGiveaways).mockResolvedValue([]);
      renderWithDJName();

      await waitFor(() => {
        expect(screen.getByText(/no giveaways found for/i)).toBeInTheDocument();
      });
    });
  });

  describe('DJ Name Input', () => {
    it('should show DJ name input field', () => {
      render(<MyPasses />);
      expect(screen.getByLabelText(/dj name/i)).toBeInTheDocument();
    });

    it('should pre-fill DJ name from localStorage', async () => {
      localStorage.setItem(DJ_NAME_KEY, 'DJ Sarah');
      render(<MyPasses />);
      await waitFor(() => {
        expect(screen.getByLabelText(/dj name/i)).toHaveValue('DJ Sarah');
      });
    });

    it('should auto-load passes when localStorage has a DJ name', async () => {
      vi.mocked(passesAPI.getMyGiveaways).mockResolvedValue(mockPasses);
      renderWithDJName('DJ Mike');

      await waitFor(() => {
        expect(passesAPI.getMyGiveaways).toHaveBeenCalledWith('DJ Mike');
      });
    });

    it('should load passes when Load button is clicked with a DJ name', async () => {
      vi.mocked(passesAPI.getMyGiveaways).mockResolvedValue(mockPasses);
      render(<MyPasses />);

      const djInput = screen.getByLabelText(/dj name/i);
      fireEvent.change(djInput, { target: { value: 'DJ Tom' } });

      const loadButton = screen.getByRole('button', { name: /load/i });
      fireEvent.click(loadButton);

      await waitFor(() => {
        expect(passesAPI.getMyGiveaways).toHaveBeenCalledWith('DJ Tom');
      });
    });

    it('should not load passes when DJ name is empty', async () => {
      render(<MyPasses />);

      const loadButton = screen.getByRole('button', { name: /load/i });
      fireEvent.click(loadButton);

      await waitFor(() => {
        expect(screen.getByText('Error: Please enter your DJ name')).toBeInTheDocument();
      });

      expect(passesAPI.getMyGiveaways).not.toHaveBeenCalled();
    });
  });

  describe('Loading and Error States', () => {
    it('should display loading message while fetching passes', async () => {
      vi.mocked(passesAPI.getMyGiveaways).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );
      renderWithDJName();

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /loading/i })).toBeDisabled();
      });
    });

    it('should display error message when API call fails', async () => {
      vi.mocked(passesAPI.getMyGiveaways).mockRejectedValue({
        detail: 'Failed to fetch giveaway history',
      });
      renderWithDJName();

      await waitFor(() => {
        expect(screen.getByText('Error: Failed to fetch giveaway history')).toBeInTheDocument();
      });
    });

    it('should display generic error message when API error has no detail', async () => {
      vi.mocked(passesAPI.getMyGiveaways).mockRejectedValue({
        detail: [{ loc: ['body'], msg: 'Invalid', type: 'error' }],
      });
      renderWithDJName();

      await waitFor(() => {
        expect(screen.getByText('Error: Failed to load giveaway history')).toBeInTheDocument();
      });
    });
  });

  describe('Multiple Passes Display', () => {
    it('should display multiple passes in order', async () => {
      vi.mocked(passesAPI.getMyGiveaways).mockResolvedValue(mockPasses);
      renderWithDJName();

      await waitFor(() => {
        const passCards = screen.getAllByText('Pass Pair');
        expect(passCards.length).toBe(2);
      });
    });

    it('should display all required information for each pass', async () => {
      vi.mocked(passesAPI.getMyGiveaways).mockResolvedValue(mockPasses);
      renderWithDJName();

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
        expect(screen.getByText('(555) 123-4567')).toBeInTheDocument();
        expect(screen.getByText('Jane Smith')).toBeInTheDocument();
        expect(screen.getByText('(555) 567-8901')).toBeInTheDocument();
      });
    });
  });

  describe('Date Formatting', () => {
    it('should format datetime with correct locale', async () => {
      const pass: PassResponse = {
        ...mockPasses[0],
        given_away_at: '2024-12-31T23:45:00',
      };
      vi.mocked(passesAPI.getMyGiveaways).mockResolvedValue([pass]);
      renderWithDJName();

      await waitFor(() => {
        expect(screen.getByText(/Dec 31, 2024/)).toBeInTheDocument();
        expect(screen.getByText(/11:45 PM/)).toBeInTheDocument();
      });
    });

    it('should handle AM times correctly', async () => {
      const pass: PassResponse = {
        ...mockPasses[0],
        given_away_at: '2024-01-15T09:30:00',
      };
      vi.mocked(passesAPI.getMyGiveaways).mockResolvedValue([pass]);
      renderWithDJName();

      await waitFor(() => {
        expect(screen.getByText(/9:30 AM/)).toBeInTheDocument();
      });
    });

    it('should handle noon correctly', async () => {
      const pass: PassResponse = {
        ...mockPasses[0],
        given_away_at: '2024-01-15T12:00:00',
      };
      vi.mocked(passesAPI.getMyGiveaways).mockResolvedValue([pass]);
      renderWithDJName();

      await waitFor(() => {
        expect(screen.getByText(/12:00 PM/)).toBeInTheDocument();
      });
    });
  });
});
