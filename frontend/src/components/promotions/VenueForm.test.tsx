import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import VenueForm from './VenueForm';
import { venuesAPI } from '../../services/api';
import type { VenueResponse } from '../../types';

// Mock the API
vi.mock('../../services/api', () => ({
  venuesAPI: {
    create: vi.fn(),
    update: vi.fn(),
  },
  adminAPI: {
    listUsers: vi.fn().mockResolvedValue([]),
  },
  promotersAPI: {
    list: vi.fn().mockResolvedValue([]),
  },
}));

const makeVenue = (overrides: Partial<VenueResponse> = {}): VenueResponse => ({
  id: 1,
  name: 'Existing Venue',
  address: '456 Old St',
  pass_call_instructions: null,
  win_frequency_days: null,
  default_wheelchair_accessible: null,
  default_age_restriction: null,
  default_num_pass_pairs: null,
  requires_phone_number: false,
  requires_email_address: false,
  staff_guest_requires_name: false,
  default_lottery_enabled: false,
  default_lottery_window_hours: 24,
  default_dj_preassign_prohibition_days: null,
  default_close_hours_before_show: null,
  has_logo: false,
  deleted: false,
  shows_have_external_promoter: false,
  owner_emails: [],
  contacts: [],
  ...overrides,
} as VenueResponse);

describe('VenueForm', () => {
  const mockOnClose = vi.fn();
  const mockOnSuccess = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Form Validation', () => {
    it('should show validation error when name is empty', async () => {
      render(
        <VenueForm venue={null} onClose={mockOnClose} onSuccess={mockOnSuccess} />
      );
      await act(async () => {});

      const submitButton = screen.getByRole('button', { name: /create/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Venue name is required')).toBeInTheDocument();
      });

      expect(venuesAPI.create).not.toHaveBeenCalled();
    });

    it('should show validation error when address is empty', async () => {
      render(
        <VenueForm venue={null} onClose={mockOnClose} onSuccess={mockOnSuccess} />
      );
      await act(async () => {});

      const nameInput = screen.getByLabelText(/venue name/i);
      fireEvent.change(nameInput, { target: { value: 'Test Venue' } });

      const submitButton = screen.getByRole('button', { name: /create/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Address is required')).toBeInTheDocument();
      });

      expect(venuesAPI.create).not.toHaveBeenCalled();
    });

    it('should not show validation errors when all required fields are filled', async () => {
      vi.mocked(venuesAPI.create).mockResolvedValue(makeVenue({ name: 'Test Venue', address: '123 Main St' }));

      render(
        <VenueForm venue={null} onClose={mockOnClose} onSuccess={mockOnSuccess} />
      );
      await act(async () => {});

      const nameInput = screen.getByLabelText(/venue name/i);
      const addressInput = screen.getByLabelText(/^address/i);

      fireEvent.change(nameInput, { target: { value: 'Test Venue' } });
      fireEvent.change(addressInput, { target: { value: '123 Main St' } });

      const submitButton = screen.getByRole('button', { name: /create/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(venuesAPI.create).toHaveBeenCalled();
      });

      expect(screen.queryByText('Venue name is required')).not.toBeInTheDocument();
      expect(screen.queryByText('Address is required')).not.toBeInTheDocument();
    });
  });

  describe('Button Interactions', () => {
    it('should call onClose when cancel button is clicked', async () => {
      render(
        <VenueForm venue={null} onClose={mockOnClose} onSuccess={mockOnSuccess} />
      );
      await act(async () => {});

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      fireEvent.click(cancelButton);

      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it('should call onClose when close (×) button is clicked', async () => {
      render(
        <VenueForm venue={null} onClose={mockOnClose} onSuccess={mockOnSuccess} />
      );
      await act(async () => {});

      const closeButton = screen.getByRole('button', { name: '×' });
      fireEvent.click(closeButton);

      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it('should disable buttons while submitting', async () => {
      vi.mocked(venuesAPI.create).mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      );

      render(
        <VenueForm venue={null} onClose={mockOnClose} onSuccess={mockOnSuccess} />
      );
      await act(async () => {});

      const nameInput = screen.getByLabelText(/venue name/i);
      const addressInput = screen.getByLabelText(/^address/i);

      fireEvent.change(nameInput, { target: { value: 'Test Venue' } });
      fireEvent.change(addressInput, { target: { value: '123 Main St' } });

      const submitButton = screen.getByRole('button', { name: /create/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(submitButton).toBeDisabled();
        expect(screen.getByRole('button', { name: /cancel/i })).toBeDisabled();
      });
    });

    it('should call onSuccess after successful creation', async () => {
      vi.mocked(venuesAPI.create).mockResolvedValue(makeVenue({ name: 'Test Venue', address: '123 Main St' }));

      render(
        <VenueForm venue={null} onClose={mockOnClose} onSuccess={mockOnSuccess} />
      );
      await act(async () => {});

      const nameInput = screen.getByLabelText(/venue name/i);
      const addressInput = screen.getByLabelText(/^address/i);

      fireEvent.change(nameInput, { target: { value: 'Test Venue' } });
      fireEvent.change(addressInput, { target: { value: '123 Main St' } });

      const submitButton = screen.getByRole('button', { name: /create/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(mockOnSuccess).toHaveBeenCalledTimes(1);
      });
    });

    it('should call update API when editing existing venue', async () => {
      const existingVenue = makeVenue();

      vi.mocked(venuesAPI.update).mockResolvedValue(makeVenue({ name: 'Updated Venue' }));

      render(
        <VenueForm
          venue={existingVenue}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      );
      await act(async () => {});

      const nameInput = screen.getByLabelText(/venue name/i);
      fireEvent.change(nameInput, { target: { value: 'Updated Venue' } });

      const submitButton = screen.getByRole('button', { name: /update/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(venuesAPI.update).toHaveBeenCalledWith(1, expect.objectContaining({
          name: 'Updated Venue',
          address: '456 Old St',
        }));
      });
    });
  });

  describe('Error Display', () => {
    it('should display API error message', async () => {
      vi.mocked(venuesAPI.create).mockRejectedValue({
        detail: 'Venue name already exists',
      });

      render(
        <VenueForm venue={null} onClose={mockOnClose} onSuccess={mockOnSuccess} />
      );
      await act(async () => {});

      const nameInput = screen.getByLabelText(/venue name/i);
      const addressInput = screen.getByLabelText(/^address/i);

      fireEvent.change(nameInput, { target: { value: 'Test Venue' } });
      fireEvent.change(addressInput, { target: { value: '123 Main St' } });

      const submitButton = screen.getByRole('button', { name: /create/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Venue name already exists')).toBeInTheDocument();
      });
    });

    it('should display field-specific validation errors from backend', async () => {
      vi.mocked(venuesAPI.create).mockRejectedValue({
        detail: [
          {
            loc: ['body', 'name'],
            msg: 'Name must be at least 3 characters',
            type: 'value_error',
          },
        ],
      });

      render(
        <VenueForm venue={null} onClose={mockOnClose} onSuccess={mockOnSuccess} />
      );
      await act(async () => {});

      const nameInput = screen.getByLabelText(/venue name/i);
      const addressInput = screen.getByLabelText(/^address/i);

      fireEvent.change(nameInput, { target: { value: 'AB' } });
      fireEvent.change(addressInput, { target: { value: '123 Main St' } });

      const submitButton = screen.getByRole('button', { name: /create/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(
          screen.getByText('Name must be at least 3 characters')
        ).toBeInTheDocument();
      });
    });

    it('should display generic error for unknown error format', async () => {
      vi.mocked(venuesAPI.create).mockRejectedValue({
        detail: { unknown: 'format' },
      });

      render(
        <VenueForm venue={null} onClose={mockOnClose} onSuccess={mockOnSuccess} />
      );
      await act(async () => {});

      const nameInput = screen.getByLabelText(/venue name/i);
      const addressInput = screen.getByLabelText(/^address/i);

      fireEvent.change(nameInput, { target: { value: 'Test Venue' } });
      fireEvent.change(addressInput, { target: { value: '123 Main St' } });

      const submitButton = screen.getByRole('button', { name: /create/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Failed to save venue')).toBeInTheDocument();
      });
    });
  });
});
