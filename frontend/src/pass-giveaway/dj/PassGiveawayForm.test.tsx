import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import PassGiveawayForm from './PassGiveawayForm';
import { passesAPI, showsAPI } from '../api';
import type { PassResponse } from '../types';

// Mock the API
vi.mock('../api', () => ({
  passesAPI: {
    giveaway: vi.fn(),
  },
  showsAPI: {
    recordAttempt: vi.fn(),
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

  const mockOnSuccess = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Giveaway Form Validation', () => {
    it('should show validation error when recipient name is empty', async () => {
      render(<PassGiveawayForm pass={mockPass} venueId={1} onSuccess={mockOnSuccess} djName="DJ Mike" />);

      const submitButton = screen.getByRole('button', { name: /give away/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Winner name is required')).toBeInTheDocument();
      });

      expect(passesAPI.giveaway).not.toHaveBeenCalled();
    });

    it('should show validation error when recipient phone is empty', async () => {
      render(<PassGiveawayForm pass={mockPass} venueId={1} onSuccess={mockOnSuccess} djName="DJ Mike" />);

      const nameInput = screen.getByLabelText(/winner name/i);
      fireEvent.change(nameInput, { target: { value: 'John Doe' } });

      const submitButton = screen.getByRole('button', { name: /give away/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Winner phone is required')).toBeInTheDocument();
      });

      expect(passesAPI.giveaway).not.toHaveBeenCalled();
    });

    it('asks for the page\'s DJ name when Give Away is clicked without one', async () => {
      const onMissingDjName = vi.fn();
      render(
        <PassGiveawayForm
          pass={mockPass}
          venueId={1}
          onSuccess={mockOnSuccess}
          djName="  "
          onMissingDjName={onMissingDjName}
        />,
      );

      const nameInput = screen.getByLabelText(/winner name/i);
      const phoneInput = screen.getByLabelText(/winner phone/i);

      fireEvent.change(nameInput, { target: { value: 'John Doe' } });
      fireEvent.change(phoneInput, { target: { value: '555-123-4567' } });

      const submitButton = screen.getByRole('button', { name: /give away/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Enter your DJ name in the DJ Name box at the top of the page')).toBeInTheDocument();
      });
      expect(onMissingDjName).toHaveBeenCalled();

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

      render(<PassGiveawayForm pass={mockPass} venueId={1} onSuccess={mockOnSuccess} djName="DJ Mike" />);

      const nameInput = screen.getByLabelText(/winner name/i);
      const phoneInput = screen.getByLabelText(/winner phone/i);

      fireEvent.change(nameInput, { target: { value: 'John Doe' } });
      fireEvent.change(phoneInput, { target: { value: '555-123-4567' } });

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

    it('asks for the page\'s DJ name when Tried is clicked without one', async () => {
      const onMissingDjName = vi.fn();
      render(
        <PassGiveawayForm
          pass={mockPass}
          venueId={1}
          onSuccess={mockOnSuccess}
          djName=""
          onMissingDjName={onMissingDjName}
        />,
      );

      const noWinnerButton = screen.getByRole('button', { name: /tried/i });
      fireEvent.click(noWinnerButton);

      await waitFor(() => {
        expect(screen.getByText('Enter your DJ name in the DJ Name box at the top of the page')).toBeInTheDocument();
      });
      expect(onMissingDjName).toHaveBeenCalled();

      expect(showsAPI.recordAttempt).not.toHaveBeenCalled();
    });

    it('should record no-winner when DJ name is provided', async () => {
      vi.mocked(showsAPI.recordAttempt).mockResolvedValue({
        id: 1,
        dj_name: 'DJ Mike',
        attempted_at: '2024-01-01T12:00:00',
      });

      render(<PassGiveawayForm pass={mockPass} venueId={1} onSuccess={mockOnSuccess} djName="DJ Mike" />);


      const noWinnerButton = screen.getByRole('button', { name: /tried/i });
      fireEvent.click(noWinnerButton);

      await waitFor(() => {
        expect(showsAPI.recordAttempt).toHaveBeenCalledWith(1, 'DJ Mike', undefined);
      });

      expect(mockOnSuccess).toHaveBeenCalled();
    });

    it('sends the giveaway page visit with a no-winner, for KALX Staff Analytics', async () => {
      vi.mocked(showsAPI.recordAttempt).mockResolvedValue({
        id: 1,
        dj_name: 'DJ Mike',
        attempted_at: '2024-01-01T12:00:00',
      });

      render(
        <PassGiveawayForm
          pass={mockPass}
          venueId={1}
          onSuccess={mockOnSuccess}
          djName="DJ Mike"
          visitId="visit-123"
        />,
      );
      fireEvent.click(screen.getByRole('button', { name: /tried/i }));

      await waitFor(() => {
        expect(showsAPI.recordAttempt).toHaveBeenCalledWith(1, 'DJ Mike', 'visit-123');
      });
      await waitFor(() => expect(mockOnSuccess).toHaveBeenCalled());
    });
  });

  describe('Layout', () => {
    it('has no DJ name field of its own', () => {
      render(<PassGiveawayForm pass={mockPass} venueId={1} onSuccess={mockOnSuccess} djName="DJ Mike" />);

      expect(screen.queryByLabelText(/dj name/i)).not.toBeInTheDocument();
    });

    it('keeps the required winner fields with Give Away, apart from Tried', () => {
      render(
        <PassGiveawayForm
          pass={mockPass}
          venueId={1}
          onSuccess={mockOnSuccess}
          djName="DJ Mike"
          requiresEmail
        />,
      );

      const callerWon = screen.getByRole('group', { name: /caller won/i });
      expect(within(callerWon).getByLabelText(/winner name \*/i)).toBeInTheDocument();
      expect(within(callerWon).getByLabelText(/winner phone \*/i)).toBeInTheDocument();
      expect(within(callerWon).getByLabelText(/winner email \*/i)).toBeInTheDocument();
      expect(within(callerWon).getByRole('button', { name: /give away/i })).toBeInTheDocument();
      expect(within(callerWon).queryByRole('button', { name: /tried/i })).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: /tried/i })).toBeInTheDocument();
    });
  });

  describe('Pre-assignment Display', () => {
    it('should display pre-assignment notice when pass is pre-assigned', async () => {
      const preassignedPass: PassResponse = {
        ...mockPass,
        preassigned_dj: 'DJ Mike',
        preassigned_date: '2024-12-31',
      };

      render(<PassGiveawayForm pass={preassignedPass} venueId={1} onSuccess={mockOnSuccess} djName="DJ Mike" />);

      expect(screen.getByText(/pre-assigned to:/i)).toBeInTheDocument();
      expect(screen.getByText(/DJ Mike/)).toBeInTheDocument();
      expect(screen.getByText(/on 2024-12-31/)).toBeInTheDocument();
    });

    it('should not display pre-assignment notice when pass is not pre-assigned', async () => {
      render(<PassGiveawayForm pass={mockPass} venueId={1} onSuccess={mockOnSuccess} djName="DJ Mike" />);

      expect(screen.queryByText(/pre-assigned to:/i)).not.toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    it('should display API error message on giveaway failure', async () => {
      vi.mocked(passesAPI.giveaway).mockRejectedValue({
        detail: 'Pass has already been given away',
      });

      render(<PassGiveawayForm pass={mockPass} venueId={1} onSuccess={mockOnSuccess} djName="DJ Mike" />);

      const nameInput = screen.getByLabelText(/winner name/i);
      const phoneInput = screen.getByLabelText(/winner phone/i);

      fireEvent.change(nameInput, { target: { value: 'John Doe' } });
      fireEvent.change(phoneInput, { target: { value: '555-123-4567' } });

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

      render(<PassGiveawayForm pass={mockPass} venueId={1} onSuccess={mockOnSuccess} djName="DJ Mike" />);

      const nameInput = screen.getByLabelText(/winner name/i);
      const phoneInput = screen.getByLabelText(/winner phone/i);

      fireEvent.change(nameInput, { target: { value: 'John Doe' } });
      fireEvent.change(phoneInput, { target: { value: '555-123-4567' } });

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

      render(<PassGiveawayForm pass={mockPass} venueId={1} onSuccess={mockOnSuccess} djName="DJ Mike" />);


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

      render(<PassGiveawayForm pass={mockPass} venueId={1} onSuccess={mockOnSuccess} djName="DJ Mike" />);

      const nameInput = screen.getByLabelText(/winner name/i);
      const phoneInput = screen.getByLabelText(/winner phone/i);

      fireEvent.change(nameInput, { target: { value: 'John Doe' } });
      fireEvent.change(phoneInput, { target: { value: '555-123-4567' } });

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

      render(<PassGiveawayForm pass={mockPass} venueId={1} onSuccess={mockOnSuccess} djName="DJ Mike" />);

      const nameInput = screen.getByLabelText(/winner name/i);
      const phoneInput = screen.getByLabelText(/winner phone/i);

      fireEvent.change(nameInput, { target: { value: 'John Doe' } });
      fireEvent.change(phoneInput, { target: { value: '555-123-4567' } });

      const submitButton = screen.getByRole('button', { name: /give away/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(nameInput).toBeDisabled();
        expect(phoneInput).toBeDisabled();
      });
    });
  });
});
