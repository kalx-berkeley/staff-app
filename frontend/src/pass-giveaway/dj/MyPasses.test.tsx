import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import MyPasses from './MyPasses';
import { passesAPI } from '../api';
import { persona, withOnAir } from './testOnAir';
import type { PassResponse } from '../types';
import { formatDateValue } from '../../common/utils';

// Mock the API
vi.mock('../api', () => ({
  passesAPI: {
    getMyGiveaways: vi.fn(),
  },
}));

const DJ_MIKE = persona(1, 'DJ Mike');

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
      guest_fallback: 'attend_alone' as const,
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
      guest_fallback: 'attend_alone' as const,
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
    vi.mocked(passesAPI.getMyGiveaways).mockReturnValue(new Promise(() => {}));
  });

  const renderWithDJName = () => render(withOnAir(<MyPasses />, DJ_MIKE));

  describe('MyPasses Display', () => {
    it('should hide passes for shows more than 3 days ago', async () => {
      const daysAgo = (days: number) => {
        const d = new Date();
        d.setDate(d.getDate() - days);
        return formatDateValue(d);
      };
      vi.mocked(passesAPI.getMyGiveaways).mockResolvedValue([
        { ...mockPasses[0], show_event_name: 'Old Show', show_date: daysAgo(4) },
        { ...mockPasses[1], show_event_name: 'Recent Show', show_date: daysAgo(3) },
      ]);
      renderWithDJName();

      expect(await screen.findByText('Recent Show')).toBeInTheDocument();
      expect(screen.queryByText('Old Show')).not.toBeInTheDocument();
    });

    it('should display all passes given away by the DJ', async () => {
      vi.mocked(passesAPI.getMyGiveaways).mockResolvedValue(mockPasses);
      renderWithDJName();

      await waitFor(() => {
        const passCards = screen.getAllByText('Pass Pair');
        expect(passCards.length).toBe(2);
      });
    });

    it("should not display the winners' names or phone numbers", async () => {
      vi.mocked(passesAPI.getMyGiveaways).mockResolvedValue(mockPasses);
      renderWithDJName();

      expect(await screen.findAllByText('Pass Pair')).toHaveLength(2);
      expect(screen.queryByText('John Doe')).not.toBeInTheDocument();
      expect(screen.queryByText('(555) 123-4567')).not.toBeInTheDocument();
      expect(screen.queryByText('Jane Smith')).not.toBeInTheDocument();
      expect(screen.queryByText('(555) 567-8901')).not.toBeInTheDocument();
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
        expect(screen.getByText(/no recent or upcoming giveaways found for/i)).toBeInTheDocument();
      });
    });
  });

  describe('Who is on air', () => {
    it("loads the on-air identity's passes", async () => {
      vi.mocked(passesAPI.getMyGiveaways).mockResolvedValue(mockPasses);
      renderWithDJName();

      await waitFor(() => expect(passesAPI.getMyGiveaways).toHaveBeenCalledWith());
      expect(screen.queryByLabelText(/dj name/i)).not.toBeInTheDocument();
    });

    it('shows nothing, without asking, when no one is on air', async () => {
      render(withOnAir(<MyPasses />, null));

      expect(
        await screen.findByText('No one is on air, so there are no passes to show.'),
      ).toBeInTheDocument();
      expect(passesAPI.getMyGiveaways).not.toHaveBeenCalled();
    });

    it('loads again when who is on air changes (an early switch)', async () => {
      vi.mocked(passesAPI.getMyGiveaways).mockResolvedValue([]);
      const { rerender } = renderWithDJName();
      await screen.findByText(/No recent or upcoming giveaways found for/);

      rerender(withOnAir(<MyPasses />, persona(2, 'DJ Next')));

      await waitFor(() => expect(passesAPI.getMyGiveaways).toHaveBeenCalledTimes(2));
      expect(await screen.findByText('DJ Next')).toBeInTheDocument();
    });
  });

  describe('Loading and Error States', () => {
    it('should display loading message while fetching passes', async () => {
      vi.mocked(passesAPI.getMyGiveaways).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );
      renderWithDJName();

      expect(await screen.findByText('Loading…')).toBeInTheDocument();
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
  });

  describe('Date Formatting', () => {
    it('should format datetime with correct locale', async () => {
      const pass: PassResponse = {
        ...mockPasses[0],
        given_away_at: '2025-01-01T07:45:00Z', // 11:45 PM PST
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
        given_away_at: '2024-01-15T17:30:00Z', // 9:30 AM PST
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
        given_away_at: '2024-01-15T20:00:00Z', // 12:00 PM PST
      };
      vi.mocked(passesAPI.getMyGiveaways).mockResolvedValue([pass]);
      renderWithDJName();

      await waitFor(() => {
        expect(screen.getByText(/12:00 PM/)).toBeInTheDocument();
      });
    });
  });
});
