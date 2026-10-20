import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import VenueForm from './VenueForm';
import { showsAPI, venuesAPI } from '../api';
import type { VenueResponse } from '../types';

// Mock the API
vi.mock('../api', () => ({
  venuesAPI: {
    create: vi.fn(),
    update: vi.fn(),
    listPromotionsStaff: vi.fn().mockResolvedValue([]),
  },
  promotersAPI: {
    list: vi.fn().mockResolvedValue([]),
  },
  showsAPI: {
    analyzeDescription: vi.fn(),
  },
}));

const makeVenue = (overrides: Partial<VenueResponse> = {}): VenueResponse => ({
  id: 1,
  name: 'Existing Venue',
  address: '456 Old St',
  show_sourcing_instructions: null,
  pass_call_instructions: null,
  win_frequency_days: null,
  default_wheelchair_accessible: null,
  venue_type: 'music', default_age_restriction: null, default_movie_rating: null,
  default_num_pass_pairs: null,
  requires_phone_number: false,
  requires_email_address: false,
  staff_guest_requires_name: false,
  default_lottery_enabled: false,
  default_lottery_window_hours: 24,
  default_dj_preassign_prohibition_days: null,
  default_close_hours_before_show: null,
  default_on_air_description: null,
  default_caller_special_instructions: null,
  has_logo: false,
  show_name_with_logo: false,
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
      let resolveCreate: (venue: VenueResponse) => void;
      vi.mocked(venuesAPI.create).mockImplementation(
        () => new Promise((resolve) => { resolveCreate = resolve; })
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

      // Resolve and let the submission finish so it doesn't leak into later tests.
      await act(async () => {
        resolveCreate(makeVenue({ name: 'Test Venue', address: '123 Main St' }));
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

  describe('Default Wheelchair Accessible', () => {
    it('should load and save Unknown, and clear it with No default', async () => {
      vi.mocked(venuesAPI.update).mockResolvedValue(makeVenue());

      render(
        <VenueForm
          venue={makeVenue({ default_wheelchair_accessible: 'unknown' })}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      );
      await act(async () => {});

      const select = screen.getByLabelText(/default wheelchair accessible/i);
      expect(select).toHaveValue('unknown');

      fireEvent.click(screen.getByRole('button', { name: /update/i }));
      await waitFor(() => {
        expect(venuesAPI.update).toHaveBeenCalledWith(1, expect.objectContaining({
          default_wheelchair_accessible: 'unknown',
        }));
      });
      await waitFor(() => expect(mockOnSuccess).toHaveBeenCalled());

      fireEvent.change(select, { target: { value: '' } });
      fireEvent.click(screen.getByRole('button', { name: /update/i }));
      await waitFor(() => {
        expect(venuesAPI.update).toHaveBeenLastCalledWith(1, expect.objectContaining({
          default_wheelchair_accessible: null,
        }));
      });
      await waitFor(() => expect(mockOnSuccess).toHaveBeenCalledTimes(2));
    });
  });

  describe('Show Name With Logo', () => {
    const nameWithLogoLabel = /show the venue name on the dj show page as well as the logo/i;

    it('should not offer the option when the venue has no logo', async () => {
      render(
        <VenueForm venue={makeVenue()} onClose={mockOnClose} onSuccess={mockOnSuccess} />
      );
      await act(async () => {});

      expect(screen.queryByLabelText(nameWithLogoLabel)).not.toBeInTheDocument();
    });

    it('should load and save the option when the venue has a logo', async () => {
      vi.mocked(venuesAPI.update).mockResolvedValue(makeVenue());

      render(
        <VenueForm
          venue={makeVenue({ has_logo: true })}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      );
      await act(async () => {});

      const checkbox = screen.getByLabelText(nameWithLogoLabel);
      expect(checkbox).not.toBeChecked();
      fireEvent.click(checkbox);

      fireEvent.click(screen.getByRole('button', { name: /update/i }));
      await waitFor(() => {
        expect(venuesAPI.update).toHaveBeenCalledWith(1, expect.objectContaining({
          show_name_with_logo: true,
        }));
      });
      await waitFor(() => expect(mockOnSuccess).toHaveBeenCalled());
    });

    it('should hide the option once the logo is removed', async () => {
      render(
        <VenueForm
          venue={makeVenue({ has_logo: true, show_name_with_logo: true })}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      );
      await act(async () => {});

      expect(screen.getByLabelText(nameWithLogoLabel)).toBeChecked();
      fireEvent.click(screen.getByRole('button', { name: /remove logo/i }));
      expect(screen.queryByLabelText(nameWithLogoLabel)).not.toBeInTheDocument();
    });
  });

  describe('Venue Type', () => {
    it('shows Default Movie Rating for a movie theater and saves it', async () => {
      vi.mocked(venuesAPI.update).mockResolvedValue(makeVenue());

      render(
        <VenueForm
          venue={makeVenue({ default_age_restriction: '21+' })}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      );
      await act(async () => {});

      expect(screen.getByLabelText(/venue type/i)).toHaveValue('music');
      expect(screen.queryByLabelText(/default movie rating/i)).not.toBeInTheDocument();

      fireEvent.change(screen.getByLabelText(/venue type/i), {
        target: { value: 'movie_theater' },
      });
      expect(screen.queryByLabelText(/default age restriction/i)).not.toBeInTheDocument();
      fireEvent.change(screen.getByLabelText(/default movie rating/i), { target: { value: 'G' } });

      fireEvent.click(screen.getByRole('button', { name: /update/i }));
      await waitFor(() => {
        expect(venuesAPI.update).toHaveBeenCalledWith(1, expect.objectContaining({
          venue_type: 'movie_theater',
          default_movie_rating: 'G',
          default_age_restriction: null,
        }));
      });
      await waitFor(() => expect(mockOnSuccess).toHaveBeenCalled());
    });
  });

  describe('Show Sourcing Instructions', () => {
    it('should load and save show sourcing instructions', async () => {
      const existingVenue = makeVenue({ show_sourcing_instructions: 'Check in mid-month.' });

      vi.mocked(venuesAPI.update).mockResolvedValue(existingVenue);

      render(
        <VenueForm
          venue={existingVenue}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      );
      await act(async () => {});

      const sourcingInput = screen.getByLabelText(/show sourcing instructions/i);
      expect(sourcingInput).toHaveValue('Check in mid-month.');
      fireEvent.change(sourcingInput, { target: { value: '  ' } });

      fireEvent.click(screen.getByRole('button', { name: /update/i }));

      await waitFor(() => {
        expect(venuesAPI.update).toHaveBeenCalledWith(1, expect.objectContaining({
          show_sourcing_instructions: null,
        }));
      });
      await waitFor(() => expect(mockOnSuccess).toHaveBeenCalled());
    });
  });

  describe('Default Show Text', () => {
    it('should load and save the default on-air description and caller instructions', async () => {
      const existingVenue = makeVenue({
        default_on_air_description: 'An evening of jazz.',
        default_caller_special_instructions: 'Bring ID.',
      });

      vi.mocked(venuesAPI.update).mockResolvedValue(existingVenue);

      render(
        <VenueForm
          venue={existingVenue}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      );
      await act(async () => {});

      const descriptionInput = screen.getByLabelText(/default on-air description/i);
      const instructionsInput = screen.getByLabelText(/default caller special instructions/i);
      expect(descriptionInput).toHaveValue('An evening of jazz.');
      expect(instructionsInput).toHaveValue('Bring ID.');
      fireEvent.change(descriptionInput, { target: { value: '  ' } });
      fireEvent.change(instructionsInput, { target: { value: '21+ only, ID at door.' } });

      fireEvent.click(screen.getByRole('button', { name: /update/i }));

      await waitFor(() => {
        expect(venuesAPI.update).toHaveBeenCalledWith(1, expect.objectContaining({
          default_on_air_description: null,
          default_caller_special_instructions: '21+ only, ID at door.',
        }));
      });
      await waitFor(() => expect(mockOnSuccess).toHaveBeenCalled());
    });

    it('should check the default on-air description for non-value-neutral language', async () => {
      vi.mocked(showsAPI.analyzeDescription).mockResolvedValue({
        findings: [
          {
            category: 'endorsement',
            severity: 'high',
            phrase: 'legendary',
            start: 4,
            end: 13,
            message: '"legendary" praises the act rather than describing it.',
            suggestion: 'Say what the act is instead of how good it is.',
          },
        ],
        sentiment_compound: 0.6,
        sentiment_positive: 0.3,
        reads_promotional: true,
        summary: '1 phrase may not be value neutral.',
      });

      render(
        <VenueForm
          venue={makeVenue()}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      );
      await act(async () => {});

      const descriptionInput = screen.getByLabelText(/default on-air description/i);
      fireEvent.change(descriptionInput, { target: { value: 'The legendary house band.' } });
      fireEvent.blur(descriptionInput);

      expect(
        await screen.findByText('This description may not be value neutral')
      ).toBeInTheDocument();
      expect(showsAPI.analyzeDescription).toHaveBeenCalledWith('The legendary house band.');
      expect(screen.getByText(/stop you from saving the venue/)).toBeInTheDocument();
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
