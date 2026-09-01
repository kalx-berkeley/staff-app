import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PassGiveawayForm from './PassGiveawayForm';
import { passesAPI, showsAPI, autocompleteAPI } from '../../services/api';
import type { PassResponse } from '../../types';

// Mock the API
vi.mock('../../services/api', () => ({
  passesAPI: {
    giveaway: vi.fn(),
  },
  showsAPI: {
    recordAttempt: vi.fn(),
  },
  autocompleteAPI: {
    getDJNames: vi.fn(),
  },
  venuePassesAPI: {
    checkWinner: vi.fn(),
  },
}));

describe('PassGiveawayForm', () => {
  const mockPass: PassResponse = {
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

  const mockOnSuccess = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(autocompleteAPI.getDJNames).mockResolvedValue([]);
    localStorage.clear();
  });

  describe('Giveaway Form Validation', () => {
    it('should show validation error when recipient name is empty', async () => {
      render(<PassGiveawayForm pass={mockPass} venueId={1} onSuccess={mockOnSuccess} />);

      const submitButton = screen.getByRole('button', { name: /give away/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Winner name is required')).toBeInTheDocument();
      });

      expect(passesAPI.giveaway).not.toHaveBeenCalled();
    });

    it('should show validation error when recipient phone is empty', async () => {
      render(<PassGiveawayForm pass={mockPass} venueId={1} onSuccess={mockOnSuccess} />);

      const nameInput = screen.getByLabelText(/winner name/i);
      fireEvent.change(nameInput, { target: { value: 'John Doe' } });

      const submitButton = screen.getByRole('button', { name: /give away/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Winner phone is required')).toBeInTheDocument();
      });

      expect(passesAPI.giveaway).not.toHaveBeenCalled();
    });

    it('should show validation error when DJ name is empty', async () => {
      render(<PassGiveawayForm pass={mockPass} venueId={1} onSuccess={mockOnSuccess} />);

      const nameInput = screen.getByLabelText(/winner name/i);
      const phoneInput = screen.getByLabelText(/winner phone/i);

      fireEvent.change(nameInput, { target: { value: 'John Doe' } });
      fireEvent.change(phoneInput, { target: { value: '555-123-4567' } });

      const submitButton = screen.getByRole('button', { name: /give away/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('DJ name is required')).toBeInTheDocument();
      });

      expect(passesAPI.giveaway).not.toHaveBeenCalled();
    });

    it('should submit form when all fields are filled', async () => {
      vi.mocked(passesAPI.giveaway).mockResolvedValue({
        ...mockPass,
        status: 'given_away',
        recipient_name: 'John Doe',
        recipient_phone: '555-123-4567',
        given_away_by_dj: 'DJ Mike',
        given_away_at: '2024-01-01T12:00:00',
      });

      render(<PassGiveawayForm pass={mockPass} venueId={1} onSuccess={mockOnSuccess} />);

      const nameInput = screen.getByLabelText(/winner name/i);
      const phoneInput = screen.getByLabelText(/winner phone/i);
      const djInput = screen.getByLabelText(/dj name/i);

      fireEvent.change(nameInput, { target: { value: 'John Doe' } });
      fireEvent.change(phoneInput, { target: { value: '555-123-4567' } });
      fireEvent.change(djInput, { target: { value: 'DJ Mike' } });

      const submitButton = screen.getByRole('button', { name: /give away/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(passesAPI.giveaway).toHaveBeenCalledWith(1, {
          recipient_name: 'John Doe',
          recipient_phone: '555-123-4567',
          recipient_email: null,
          given_away_by_dj: 'DJ Mike',
        });
      });

      expect(mockOnSuccess).toHaveBeenCalled();
    });

    it('should show validation error for no-winner when DJ name is empty', async () => {
      render(<PassGiveawayForm pass={mockPass} venueId={1} onSuccess={mockOnSuccess} />);

      const noWinnerButton = screen.getByRole('button', { name: /tried/i });
      fireEvent.click(noWinnerButton);

      await waitFor(() => {
        expect(screen.getByText('DJ name is required')).toBeInTheDocument();
      });

      expect(showsAPI.recordAttempt).not.toHaveBeenCalled();
    });

    it('should record no-winner when DJ name is provided', async () => {
      vi.mocked(showsAPI.recordAttempt).mockResolvedValue({
        id: 1,
        dj_name: 'DJ Mike',
        attempted_at: '2024-01-01T12:00:00',
      });

      render(<PassGiveawayForm pass={mockPass} venueId={1} onSuccess={mockOnSuccess} />);

      const djInput = screen.getByLabelText(/dj name/i);
      fireEvent.change(djInput, { target: { value: 'DJ Mike' } });

      const noWinnerButton = screen.getByRole('button', { name: /tried/i });
      fireEvent.click(noWinnerButton);

      await waitFor(() => {
        expect(showsAPI.recordAttempt).toHaveBeenCalledWith(1, 'DJ Mike');
      });

      expect(mockOnSuccess).toHaveBeenCalled();
    });
  });

  describe('Autocomplete Behavior', () => {
    it('should load DJ names on mount', async () => {
      vi.mocked(autocompleteAPI.getDJNames).mockResolvedValue(['DJ Mike', 'DJ Sarah', 'DJ Tom']);

      render(<PassGiveawayForm pass={mockPass} venueId={1} onSuccess={mockOnSuccess} />);

      await waitFor(() => {
        expect(autocompleteAPI.getDJNames).toHaveBeenCalled();
      });
    });

    it('should show autocomplete suggestions when typing DJ name', async () => {
      vi.mocked(autocompleteAPI.getDJNames).mockResolvedValue(['DJ Mike', 'DJ Sarah', 'DJ Tom']);

      render(<PassGiveawayForm pass={mockPass} venueId={1} onSuccess={mockOnSuccess} />);

      await waitFor(() => {
        expect(autocompleteAPI.getDJNames).toHaveBeenCalled();
      });

      const djInput = screen.getByLabelText(/dj name/i);
      fireEvent.change(djInput, { target: { value: 'mike' } });

      await waitFor(() => {
        expect(screen.getByText('DJ Mike')).toBeInTheDocument();
      });

      expect(screen.queryByText('DJ Sarah')).not.toBeInTheDocument();
      expect(screen.queryByText('DJ Tom')).not.toBeInTheDocument();
    });

    it('should filter autocomplete suggestions case-insensitively', async () => {
      vi.mocked(autocompleteAPI.getDJNames).mockResolvedValue(['DJ Mike', 'DJ Sarah', 'DJ Tom']);

      render(<PassGiveawayForm pass={mockPass} venueId={1} onSuccess={mockOnSuccess} />);

      await waitFor(() => {
        expect(autocompleteAPI.getDJNames).toHaveBeenCalled();
      });

      const djInput = screen.getByLabelText(/dj name/i);
      fireEvent.change(djInput, { target: { value: 'SARAH' } });

      await waitFor(() => {
        expect(screen.getByText('DJ Sarah')).toBeInTheDocument();
      });
    });

    it('should select DJ name when clicking autocomplete item', async () => {
      vi.mocked(autocompleteAPI.getDJNames).mockResolvedValue(['DJ Mike', 'DJ Sarah', 'DJ Tom']);

      render(<PassGiveawayForm pass={mockPass} venueId={1} onSuccess={mockOnSuccess} />);

      await waitFor(() => {
        expect(autocompleteAPI.getDJNames).toHaveBeenCalled();
      });

      const djInput = screen.getByLabelText(/dj name/i);
      fireEvent.change(djInput, { target: { value: 'mike' } });

      await waitFor(() => {
        expect(screen.getByText('DJ Mike')).toBeInTheDocument();
      });

      const autocompleteItem = screen.getByText('DJ Mike');
      fireEvent.mouseDown(autocompleteItem);

      expect(djInput).toHaveValue('DJ Mike');
    });

    it('should hide autocomplete when input is empty', async () => {
      vi.mocked(autocompleteAPI.getDJNames).mockResolvedValue(['DJ Mike', 'DJ Sarah', 'DJ Tom']);

      render(<PassGiveawayForm pass={mockPass} venueId={1} onSuccess={mockOnSuccess} />);

      await waitFor(() => {
        expect(autocompleteAPI.getDJNames).toHaveBeenCalled();
      });

      const djInput = screen.getByLabelText(/dj name/i);
      fireEvent.change(djInput, { target: { value: 'mike' } });

      await waitFor(() => {
        expect(screen.getByText('DJ Mike')).toBeInTheDocument();
      });

      fireEvent.change(djInput, { target: { value: '' } });

      await waitFor(() => {
        expect(screen.queryByText('DJ Mike')).not.toBeInTheDocument();
      });
    });

    it('should handle autocomplete API failure gracefully', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      vi.mocked(autocompleteAPI.getDJNames).mockRejectedValue(new Error('API Error'));

      render(<PassGiveawayForm pass={mockPass} venueId={1} onSuccess={mockOnSuccess} />);

      await waitFor(() => {
        expect(screen.getByLabelText(/dj name/i)).toBeInTheDocument();
      });

      const djInput = screen.getByLabelText(/dj name/i);
      fireEvent.change(djInput, { target: { value: 'DJ Mike' } });

      expect(screen.queryByText('DJ Mike')).not.toBeInTheDocument();

      expect(consoleErrorSpy).toHaveBeenCalledWith('Failed to load DJ names:', expect.any(Error));
      consoleErrorSpy.mockRestore();
    });
  });

  describe('Pre-assignment Display', () => {
    it('should display pre-assignment notice when pass is pre-assigned', async () => {
      const preassignedPass: PassResponse = {
        ...mockPass,
        preassigned_dj: 'DJ Mike',
        preassigned_date: '2024-12-31',
      };

      render(<PassGiveawayForm pass={preassignedPass} venueId={1} onSuccess={mockOnSuccess} />);

      await waitFor(() => {
        expect(autocompleteAPI.getDJNames).toHaveBeenCalled();
      });

      expect(screen.getByText(/pre-assigned to:/i)).toBeInTheDocument();
      expect(screen.getByText(/DJ Mike/)).toBeInTheDocument();
      expect(screen.getByText(/on 2024-12-31/)).toBeInTheDocument();
    });

    it('should not display pre-assignment notice when pass is not pre-assigned', async () => {
      render(<PassGiveawayForm pass={mockPass} venueId={1} onSuccess={mockOnSuccess} />);

      await waitFor(() => {
        expect(autocompleteAPI.getDJNames).toHaveBeenCalled();
      });

      expect(screen.queryByText(/pre-assigned to:/i)).not.toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    it('should display API error message on giveaway failure', async () => {
      vi.mocked(passesAPI.giveaway).mockRejectedValue({
        detail: 'Pass has already been given away',
      });

      render(<PassGiveawayForm pass={mockPass} venueId={1} onSuccess={mockOnSuccess} />);

      const nameInput = screen.getByLabelText(/winner name/i);
      const phoneInput = screen.getByLabelText(/winner phone/i);
      const djInput = screen.getByLabelText(/dj name/i);

      fireEvent.change(nameInput, { target: { value: 'John Doe' } });
      fireEvent.change(phoneInput, { target: { value: '555-123-4567' } });
      fireEvent.change(djInput, { target: { value: 'DJ Mike' } });

      const submitButton = screen.getByRole('button', { name: /give away/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Pass has already been given away')).toBeInTheDocument();
      });

      expect(mockOnSuccess).not.toHaveBeenCalled();
    });

    it('should display generic error message when API error has no detail', async () => {
      vi.mocked(passesAPI.giveaway).mockRejectedValue({
        detail: [{ loc: ['body'], msg: 'Invalid data', type: 'value_error' }],
      });

      render(<PassGiveawayForm pass={mockPass} venueId={1} onSuccess={mockOnSuccess} />);

      const nameInput = screen.getByLabelText(/winner name/i);
      const phoneInput = screen.getByLabelText(/winner phone/i);
      const djInput = screen.getByLabelText(/dj name/i);

      fireEvent.change(nameInput, { target: { value: 'John Doe' } });
      fireEvent.change(phoneInput, { target: { value: '555-123-4567' } });
      fireEvent.change(djInput, { target: { value: 'DJ Mike' } });

      const submitButton = screen.getByRole('button', { name: /give away/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Failed to record giveaway')).toBeInTheDocument();
      });
    });

    it('should display API error message on no-winner failure', async () => {
      vi.mocked(showsAPI.recordAttempt).mockRejectedValue({
        detail: 'Show is closed',
      });

      render(<PassGiveawayForm pass={mockPass} venueId={1} onSuccess={mockOnSuccess} />);

      const djInput = screen.getByLabelText(/dj name/i);
      fireEvent.change(djInput, { target: { value: 'DJ Mike' } });

      const noWinnerButton = screen.getByRole('button', { name: /tried/i });
      fireEvent.click(noWinnerButton);

      await waitFor(() => {
        expect(screen.getByText('Show is closed')).toBeInTheDocument();
      });
    });
  });

  describe('Loading States', () => {
    it('should disable buttons while submitting giveaway', async () => {
      vi.mocked(passesAPI.giveaway).mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      );

      render(<PassGiveawayForm pass={mockPass} venueId={1} onSuccess={mockOnSuccess} />);

      const nameInput = screen.getByLabelText(/winner name/i);
      const phoneInput = screen.getByLabelText(/winner phone/i);
      const djInput = screen.getByLabelText(/dj name/i);

      fireEvent.change(nameInput, { target: { value: 'John Doe' } });
      fireEvent.change(phoneInput, { target: { value: '555-123-4567' } });
      fireEvent.change(djInput, { target: { value: 'DJ Mike' } });

      const submitButton = screen.getByRole('button', { name: /give away/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /saving\.\.\./i })).toBeDisabled();
      });
    });

    it('should disable inputs while submitting', async () => {
      vi.mocked(passesAPI.giveaway).mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      );

      render(<PassGiveawayForm pass={mockPass} venueId={1} onSuccess={mockOnSuccess} />);

      const nameInput = screen.getByLabelText(/winner name/i);
      const phoneInput = screen.getByLabelText(/winner phone/i);
      const djInput = screen.getByLabelText(/dj name/i);

      fireEvent.change(nameInput, { target: { value: 'John Doe' } });
      fireEvent.change(phoneInput, { target: { value: '555-123-4567' } });
      fireEvent.change(djInput, { target: { value: 'DJ Mike' } });

      const submitButton = screen.getByRole('button', { name: /give away/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(nameInput).toBeDisabled();
        expect(phoneInput).toBeDisabled();
        expect(djInput).toBeDisabled();
      });
    });
  });
});
