import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ShowForm from './ShowForm';
import { showsAPI, venuesAPI, venuesMyAPI } from '../api';
import type { DescriptionAnalysis, VenueResponse } from '../types';

// Mock the API
vi.mock('../api', () => ({
  showsAPI: {
    create: vi.fn(),
    update: vi.fn(),
    get: vi.fn(),
    publish: vi.fn(),
    listGenres: vi.fn(),
    analyzeDescription: vi.fn(),
  },
  venuesAPI: {
    list: vi.fn(),
  },
  venuesMyAPI: {
    listMy: vi.fn(),
  },
  promotersAPI: {
    list: vi.fn().mockResolvedValue([]),
  },
}));

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe('ShowForm', () => {
  const mockVenues: VenueResponse[] = [
    { id: 1, name: 'Venue A', address: '123 Main St', show_sourcing_instructions: null, pass_call_instructions: null, win_frequency_days: null, default_wheelchair_accessible: null, venue_type: 'music', default_age_restriction: null, default_movie_rating: null, default_num_pass_pairs: null, requires_phone_number: false, requires_email_address: false, staff_guest_requires_name: false, default_lottery_enabled: false, default_lottery_window_hours: 24, default_dj_preassign_prohibition_days: null, default_close_hours_before_show: null, default_on_air_description: null, default_caller_special_instructions: null, has_logo: false, deleted: false, shows_have_external_promoter: false, owner_emails: [], contacts: [] },
    { id: 2, name: 'Venue B', address: '456 Oak Ave', show_sourcing_instructions: null, pass_call_instructions: null, win_frequency_days: null, default_wheelchair_accessible: null, venue_type: 'music', default_age_restriction: null, default_movie_rating: null, default_num_pass_pairs: null, requires_phone_number: false, requires_email_address: false, staff_guest_requires_name: false, default_lottery_enabled: false, default_lottery_window_hours: 24, default_dj_preassign_prohibition_days: null, default_close_hours_before_show: null, default_on_air_description: null, default_caller_special_instructions: null, has_logo: false, deleted: false, shows_have_external_promoter: false, owner_emails: [], contacts: [] },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(venuesAPI.list).mockResolvedValue(mockVenues);
    vi.mocked(venuesMyAPI.listMy).mockResolvedValue(mockVenues);
    vi.mocked(showsAPI.listGenres).mockResolvedValue([]);
  });

  const renderShowForm = (initialPath = '/promotions/shows/new') => {
    return render(
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/promotions/shows/new" element={<ShowForm />} />
          <Route path="/promotions/shows/:id/edit" element={<ShowForm />} />
        </Routes>
      </MemoryRouter>
    );
  };

  describe('Form Validation', () => {
    it('should show validation error when event name is empty', async () => {
      renderShowForm();

      await waitFor(() => {
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
      });

      const submitButton = screen.getByRole('button', { name: /save draft/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Event name is required')).toBeInTheDocument();
      });

      expect(showsAPI.create).not.toHaveBeenCalled();
    });

    it('should show validation error when venue is not selected', async () => {
      renderShowForm();

      await waitFor(() => {
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
      });

      const eventNameInput = screen.getByLabelText(/event name/i);
      const genreInput = screen.getByLabelText(/genre/i);

      eventNameInput.textContent = 'Test Event';
      fireEvent.input(eventNameInput);
      fireEvent.change(genreInput, { target: { value: 'Rock' } });

      const submitButton = screen.getByRole('button', { name: /save draft/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Venue is required')).toBeInTheDocument();
      });
    });

    it('should show validation error when date is empty', async () => {
      renderShowForm();

      await waitFor(() => {
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
      });

      const eventNameInput = screen.getByLabelText(/event name/i);
      const genreInput = screen.getByLabelText(/genre/i);
      const venueSelect = screen.getByRole('combobox', { name: /Venue/ });

      eventNameInput.textContent = 'Test Event';
      fireEvent.input(eventNameInput);
      fireEvent.change(genreInput, { target: { value: 'Rock' } });
      fireEvent.change(venueSelect, { target: { value: '1' } });

      const submitButton = screen.getByRole('button', { name: /save draft/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Show date is required')).toBeInTheDocument();
      });
    });

    it('should show validation error when time is empty', async () => {
      renderShowForm();

      await waitFor(() => {
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
      });

      const eventNameInput = screen.getByLabelText(/event name/i);
      const genreInput = screen.getByLabelText(/genre/i);
      const venueSelect = screen.getByRole('combobox', { name: /Venue/ });
      const dateInput = screen.getByLabelText(/show date/i);
      const timeInput = screen.getByLabelText(/show time/i);

      eventNameInput.textContent = 'Test Event';
      fireEvent.input(eventNameInput);
      fireEvent.change(genreInput, { target: { value: 'Rock' } });
      fireEvent.change(venueSelect, { target: { value: '1' } });
      fireEvent.change(dateInput, { target: { value: '2024-12-31' } });
      // Show time defaults to 7:00 PM; clear it to exercise the required-field validation.
      fireEvent.change(timeInput, { target: { value: '' } });

      const submitButton = screen.getByRole('button', { name: /save draft/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Show time is required')).toBeInTheDocument();
      });
    });

    it('should show validation error when multi-day end date is before start date', async () => {
      renderShowForm();

      await waitFor(() => {
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
      });

      const eventNameInput = screen.getByLabelText(/event name/i);
      const genreInput = screen.getByLabelText(/genre/i);
      const venueSelect = screen.getByRole('combobox', { name: /Venue/ });

      eventNameInput.textContent = 'Test Event';
      fireEvent.input(eventNameInput);
      fireEvent.change(genreInput, { target: { value: 'Rock' } });
      fireEvent.change(venueSelect, { target: { value: '1' } });

      fireEvent.click(screen.getByRole('button', { name: /multi-day/i }));

      const startDateInput = screen.getByLabelText(/start date/i);
      const endDateInput = screen.getByLabelText(/end date/i);
      fireEvent.change(startDateInput, { target: { value: '2024-12-31' } });
      fireEvent.change(endDateInput, { target: { value: '2024-12-30' } });

      const submitButton = screen.getByRole('button', { name: /save draft/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(
          screen.getByText('End date must be on or after the start date')
        ).toBeInTheDocument();
      });

      expect(showsAPI.create).not.toHaveBeenCalled();
    });
  });

  describe('Button Interactions', () => {
    it('should navigate back when cancel button is clicked', async () => {
      renderShowForm();

      await waitFor(() => {
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
      });

      const cancelButtons = screen.getAllByRole('button', { name: /cancel/i });
      fireEvent.click(cancelButtons[0]);

      expect(mockNavigate).toHaveBeenCalledWith('/promotions/shows');
    });

    it('should disable buttons while submitting', async () => {
      vi.mocked(showsAPI.create).mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      );

      renderShowForm();

      await waitFor(() => {
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
      });

      const eventNameInput = screen.getByLabelText(/event name/i);
      const genreInput = screen.getByLabelText(/genre/i);
      const venueSelect = screen.getByRole('combobox', { name: /Venue/ });
      const dateInput = screen.getByLabelText(/show date/i);
      const timeInput = screen.getByLabelText(/show time/i);

      eventNameInput.textContent = 'Test Event';
      fireEvent.input(eventNameInput);
      fireEvent.change(genreInput, { target: { value: 'Rock' } });
      fireEvent.change(venueSelect, { target: { value: '1' } });
      fireEvent.change(dateInput, { target: { value: '2024-12-31' } });
      fireEvent.change(timeInput, { target: { value: '20:00' } });
      fireEvent.change(screen.getByLabelText(/close date/i), { target: { value: '2024-12-31' } });
      fireEvent.change(screen.getByLabelText(/close time/i), { target: { value: '18:00' } });

      const submitButton = screen.getByRole('button', { name: /save draft/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(submitButton).toBeDisabled();
      });
    });

    it('should navigate to shows list after successful creation', async () => {
      vi.mocked(showsAPI.create).mockResolvedValue({
        id: 1,
        event_name: 'Test Event',
        genre: ['Rock'],
        venue: mockVenues[0],
        show_date: '2024-12-31',
        show_time: '20:00',
        show_start_date: null,
        on_air_description: null,
        caller_special_instructions: null,
        age_restriction: 'all_ages',
        movie_rating: null,
        wheelchair_accessible: 'yes',
        num_pass_pairs: 1,
        extra_staff_passes: 0,
        num_staff_passes: 1,
        promotions_contacts: [],
        attempts: [],
        status: 'draft',
        passes: [],
        available_pair_count: 1,
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
      });

      renderShowForm();

      await waitFor(() => {
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
      });

      const eventNameInput = screen.getByLabelText(/event name/i);
      const genreInput = screen.getByLabelText(/genre/i);
      const venueSelect = screen.getByRole('combobox', { name: /Venue/ });
      const dateInput = screen.getByLabelText(/show date/i);
      const timeInput = screen.getByLabelText(/show time/i);

      eventNameInput.textContent = 'Test Event';
      fireEvent.input(eventNameInput);
      fireEvent.change(genreInput, { target: { value: 'Rock' } });
      fireEvent.change(venueSelect, { target: { value: '1' } });
      fireEvent.change(dateInput, { target: { value: '2024-12-31' } });
      fireEvent.change(timeInput, { target: { value: '20:00' } });
      fireEvent.change(screen.getByLabelText(/close date/i), { target: { value: '2024-12-31' } });
      fireEvent.change(screen.getByLabelText(/close time/i), { target: { value: '18:00' } });

      const submitButton = screen.getByRole('button', { name: /save draft/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/promotions/shows');
      });
    });

    it("should go to the new show's page after publishing it", async () => {
      vi.mocked(showsAPI.create).mockResolvedValue(
        { id: 42 } as Awaited<ReturnType<typeof showsAPI.create>>,
      );
      vi.mocked(showsAPI.publish).mockResolvedValue(
        { id: 42 } as Awaited<ReturnType<typeof showsAPI.publish>>,
      );

      renderShowForm();

      await waitFor(() => {
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
      });

      const eventNameInput = screen.getByLabelText(/event name/i);
      eventNameInput.textContent = 'Test Event';
      fireEvent.input(eventNameInput);
      fireEvent.change(screen.getByLabelText(/genre/i), { target: { value: 'Rock' } });
      fireEvent.change(screen.getByRole('combobox', { name: /Venue/ }), { target: { value: '1' } });
      fireEvent.change(screen.getByLabelText(/show date/i), { target: { value: '2024-12-31' } });
      fireEvent.change(screen.getByLabelText(/show time/i), { target: { value: '20:00' } });
      fireEvent.change(screen.getByLabelText(/close date/i), { target: { value: '2024-12-31' } });
      fireEvent.change(screen.getByLabelText(/close time/i), { target: { value: '18:00' } });

      fireEvent.click(screen.getByRole('button', { name: /publish show/i }));

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/promotions/shows/42');
      });
      expect(showsAPI.publish).toHaveBeenCalledWith(42);
    });

    it('should send extra staff passes and show the total', async () => {
      vi.mocked(showsAPI.create).mockResolvedValue(
        { id: 1 } as Awaited<ReturnType<typeof showsAPI.create>>,
      );

      renderShowForm();

      await waitFor(() => {
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
      });

      const eventNameInput = screen.getByLabelText(/event name/i);
      eventNameInput.textContent = 'Test Event';
      fireEvent.input(eventNameInput);
      fireEvent.change(screen.getByLabelText(/genre/i), { target: { value: 'Rock' } });
      fireEvent.change(screen.getByRole('combobox', { name: /Venue/ }), { target: { value: '1' } });
      fireEvent.change(screen.getByLabelText(/show date/i), { target: { value: '2024-12-31' } });
      fireEvent.change(screen.getByLabelText(/show time/i), { target: { value: '20:00' } });
      fireEvent.change(screen.getByLabelText(/close date/i), { target: { value: '2024-12-31' } });
      fireEvent.change(screen.getByLabelText(/close time/i), { target: { value: '18:00' } });

      fireEvent.change(screen.getByLabelText(/number of pass pairs/i), { target: { value: '3' } });
      expect(screen.queryByLabelText(/extra staff passes/i)).not.toBeInTheDocument();
      fireEvent.click(screen.getByRole('button', { name: /advanced/i }));
      fireEvent.change(screen.getByLabelText(/extra staff passes/i), { target: { value: '2' } });
      expect(screen.getByText(/5 staff passes in total/)).toBeInTheDocument();

      fireEvent.click(screen.getByRole('button', { name: /save draft/i }));

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/promotions/shows');
      });
      expect(showsAPI.create).toHaveBeenCalledWith(
        expect.objectContaining({ num_pass_pairs: 3, extra_staff_passes: 2 }),
      );
    });
  });

  describe('Error Display', () => {
    it('should display API error message', async () => {
      vi.mocked(showsAPI.create).mockRejectedValue({
        detail: 'Show date must be in the future',
      });

      renderShowForm();

      await waitFor(() => {
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
      });

      const eventNameInput = screen.getByLabelText(/event name/i);
      const genreInput = screen.getByLabelText(/genre/i);
      const venueSelect = screen.getByRole('combobox', { name: /Venue/ });
      const dateInput = screen.getByLabelText(/show date/i);
      const timeInput = screen.getByLabelText(/show time/i);

      eventNameInput.textContent = 'Test Event';
      fireEvent.input(eventNameInput);
      fireEvent.change(genreInput, { target: { value: 'Rock' } });
      fireEvent.change(venueSelect, { target: { value: '1' } });
      fireEvent.change(dateInput, { target: { value: '2024-12-31' } });
      fireEvent.change(timeInput, { target: { value: '20:00' } });
      fireEvent.change(screen.getByLabelText(/close date/i), { target: { value: '2024-12-31' } });
      fireEvent.change(screen.getByLabelText(/close time/i), { target: { value: '18:00' } });

      const submitButton = screen.getByRole('button', { name: /save draft/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(
          screen.getByText('Show date must be in the future')
        ).toBeInTheDocument();
      });
    });

    it('should display field-specific validation errors from backend', async () => {
      vi.mocked(showsAPI.create).mockRejectedValue({
        detail: [
          {
            loc: ['body', 'num_pass_pairs'],
            msg: 'Value must be between 1 and 5',
            type: 'value_error',
          },
        ],
      });

      renderShowForm();

      await waitFor(() => {
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
      });

      const eventNameInput = screen.getByLabelText(/event name/i);
      const genreInput = screen.getByLabelText(/genre/i);
      const venueSelect = screen.getByRole('combobox', { name: /Venue/ });
      const dateInput = screen.getByLabelText(/show date/i);
      const timeInput = screen.getByLabelText(/show time/i);

      eventNameInput.textContent = 'Test Event';
      fireEvent.input(eventNameInput);
      fireEvent.change(genreInput, { target: { value: 'Rock' } });
      fireEvent.change(venueSelect, { target: { value: '1' } });
      fireEvent.change(dateInput, { target: { value: '2024-12-31' } });
      fireEvent.change(timeInput, { target: { value: '20:00' } });
      fireEvent.change(screen.getByLabelText(/close date/i), { target: { value: '2024-12-31' } });
      fireEvent.change(screen.getByLabelText(/close time/i), { target: { value: '18:00' } });

      const submitButton = screen.getByRole('button', { name: /save draft/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(
          screen.getByText('Value must be between 1 and 5')
        ).toBeInTheDocument();
      });
    });
  });

  describe('On-Air Description Language Check', () => {
    const analysisWithFindings: DescriptionAnalysis = {
      findings: [
        {
          category: 'endorsement',
          severity: 'high',
          phrase: 'legendary',
          start: 5,
          end: 14,
          message: '"legendary" praises the act rather than describing it.',
          suggestion: 'Say what the act is instead of how good it is.',
        },
        {
          category: 'terminology',
          severity: 'high',
          phrase: 'tickets',
          start: 20,
          end: 27,
          message: '"tickets" cannot be used on air.',
          suggestion: 'We give away passes, not tickets. Use "pass" or "passes".',
        },
      ],
      sentiment_compound: 0.7,
      sentiment_positive: 0.3,
      reads_promotional: true,
      summary: '2 phrases may not be value neutral.',
    };

    const cleanAnalysis: DescriptionAnalysis = {
      findings: [],
      sentiment_compound: 0.0,
      sentiment_positive: 0.0,
      reads_promotional: false,
      summary: 'No non-value-neutral language detected.',
    };

    const blurDescription = async (text: string) => {
      renderShowForm();

      await waitFor(() => {
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
      });

      const description = screen.getByLabelText(/on-air description/i);
      fireEvent.change(description, { target: { value: text } });
      fireEvent.blur(description);

      // Wait for the analysis request (if any) to settle so its resulting
      // state update lands inside act() instead of leaking into the next test.
      await waitFor(() => {
        expect(
          screen.queryByText(/Checking the description for non-value-neutral language/)
        ).not.toBeInTheDocument();
      });

      return description;
    };

    it('should analyze the description when the field loses focus', async () => {
      vi.mocked(showsAPI.analyzeDescription).mockResolvedValue(analysisWithFindings);

      await blurDescription('This legendary band has tickets available.');

      await waitFor(() => {
        expect(showsAPI.analyzeDescription).toHaveBeenCalledWith(
          'This legendary band has tickets available.'
        );
      });
    });

    it('should warn about promotional language and the word tickets', async () => {
      vi.mocked(showsAPI.analyzeDescription).mockResolvedValue(analysisWithFindings);

      await blurDescription('This legendary band has tickets available.');

      await waitFor(() => {
        expect(
          screen.getByText('This description may not be value neutral')
        ).toBeInTheDocument();
      });
      expect(
        screen.getByText('"legendary" praises the act rather than describing it.')
      ).toBeInTheDocument();
      expect(screen.getByText('"tickets" cannot be used on air.')).toBeInTheDocument();
      expect(
        screen.getByText(/We give away passes, not tickets/)
      ).toBeInTheDocument();
    });

    it('should say the warning may be wrong and can be ignored', async () => {
      vi.mocked(showsAPI.analyzeDescription).mockResolvedValue(analysisWithFindings);

      await blurDescription('This legendary band has tickets available.');

      await waitFor(() => {
        expect(screen.getByText(/automated and it can be wrong/)).toBeInTheDocument();
      });
      expect(screen.getByText(/ignore this warning/)).toBeInTheDocument();
    });

    it('should let the warning be dismissed', async () => {
      vi.mocked(showsAPI.analyzeDescription).mockResolvedValue(analysisWithFindings);

      await blurDescription('This legendary band has tickets available.');

      await waitFor(() => {
        expect(
          screen.getByText('This description may not be value neutral')
        ).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /dismiss description warning/i }));

      expect(
        screen.queryByText('This description may not be value neutral')
      ).not.toBeInTheDocument();
    });

    it('should not warn when the description is value neutral', async () => {
      vi.mocked(showsAPI.analyzeDescription).mockResolvedValue(cleanAnalysis);

      await blurDescription('Fake Fruit plays the Rickshaw Stop on March 3.');

      await waitFor(() => {
        expect(
          screen.getByText('No non-value-neutral language detected.')
        ).toBeInTheDocument();
      });
      expect(
        screen.queryByText('This description may not be value neutral')
      ).not.toBeInTheDocument();
    });

    it('should not re-analyze unchanged text on a second blur', async () => {
      vi.mocked(showsAPI.analyzeDescription).mockResolvedValue(cleanAnalysis);

      const description = await blurDescription('Fake Fruit plays on March 3.');

      await waitFor(() => {
        expect(showsAPI.analyzeDescription).toHaveBeenCalledTimes(1);
      });

      fireEvent.blur(description);

      expect(showsAPI.analyzeDescription).toHaveBeenCalledTimes(1);
    });

    it('should not analyze an empty description', async () => {
      vi.mocked(showsAPI.analyzeDescription).mockResolvedValue(cleanAnalysis);

      await blurDescription('   ');

      expect(showsAPI.analyzeDescription).not.toHaveBeenCalled();
    });

    it('should stay silent when the analysis request fails', async () => {
      vi.mocked(showsAPI.analyzeDescription).mockRejectedValue(new Error('boom'));

      await blurDescription('This legendary band has tickets available.');

      await waitFor(() => {
        expect(showsAPI.analyzeDescription).toHaveBeenCalled();
      });
      expect(
        screen.queryByText('This description may not be value neutral')
      ).not.toBeInTheDocument();
    });
  });

  describe('Venue Text Defaults', () => {
    const venuesWithText: VenueResponse[] = [
      {
        ...mockVenues[0],
        default_on_air_description: 'Venue A description',
        default_caller_special_instructions: 'Venue A instructions',
      },
      {
        ...mockVenues[1],
        default_on_air_description: 'Venue B description',
        default_caller_special_instructions: null,
      },
    ];

    const renderAndSelectVenue = async (venueId: string) => {
      vi.mocked(venuesMyAPI.listMy).mockResolvedValue(venuesWithText);
      renderShowForm();
      await waitFor(() => {
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
      });
      fireEvent.change(screen.getByRole('combobox', { name: /Venue/ }), {
        target: { value: venueId },
      });
    };

    it('fills the description and caller instructions from the venue', async () => {
      await renderAndSelectVenue('1');

      expect(await screen.findByLabelText(/on-air description/i)).toHaveValue(
        'Venue A description'
      );
      expect(screen.getByLabelText(/caller special instructions/i)).toHaveValue(
        'Venue A instructions'
      );
    });

    it("replaces the previous venue's untouched defaults when the venue changes", async () => {
      await renderAndSelectVenue('1');
      fireEvent.change(screen.getByRole('combobox', { name: /Venue/ }), {
        target: { value: '2' },
      });

      expect(await screen.findByLabelText(/on-air description/i)).toHaveValue(
        'Venue B description'
      );
      expect(screen.getByLabelText(/caller special instructions/i)).toHaveValue('');
    });

    it('keeps text the user wrote when the venue changes', async () => {
      await renderAndSelectVenue('1');
      fireEvent.change(screen.getByLabelText(/caller special instructions/i), {
        target: { value: 'Bring ID' },
      });
      fireEvent.change(screen.getByRole('combobox', { name: /Venue/ }), {
        target: { value: '2' },
      });

      expect(await screen.findByLabelText(/on-air description/i)).toHaveValue(
        'Venue B description'
      );
      expect(screen.getByLabelText(/caller special instructions/i)).toHaveValue('Bring ID');
    });
  });

  describe('Wheelchair Accessible', () => {
    it("starts as Yes and takes the venue's default, including Unknown", async () => {
      vi.mocked(venuesMyAPI.listMy).mockResolvedValue([
        { ...mockVenues[0], default_wheelchair_accessible: 'unknown' },
        mockVenues[1],
      ]);
      renderShowForm();
      await waitFor(() => {
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
      });
      const wheelchair = screen.getByLabelText(/wheelchair accessible/i);
      expect(wheelchair).toHaveValue('yes');

      fireEvent.change(screen.getByRole('combobox', { name: /Venue/ }), { target: { value: '1' } });
      expect(await screen.findByLabelText(/wheelchair accessible/i)).toHaveValue('unknown');

      // A venue with no default leaves it as it is
      fireEvent.change(screen.getByRole('combobox', { name: /Venue/ }), { target: { value: '2' } });
      expect(await screen.findByLabelText(/wheelchair accessible/i)).toHaveValue('unknown');
    });

    it('sends the chosen value', async () => {
      vi.mocked(showsAPI.create).mockResolvedValue(
        { id: 1 } as Awaited<ReturnType<typeof showsAPI.create>>,
      );

      renderShowForm();

      await waitFor(() => {
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
      });

      const eventNameInput = screen.getByLabelText(/event name/i);
      eventNameInput.textContent = 'Test Event';
      fireEvent.input(eventNameInput);
      fireEvent.change(screen.getByLabelText(/genre/i), { target: { value: 'Rock' } });
      fireEvent.change(screen.getByRole('combobox', { name: /Venue/ }), { target: { value: '1' } });
      fireEvent.change(screen.getByLabelText(/show date/i), { target: { value: '2024-12-31' } });
      fireEvent.change(screen.getByLabelText(/show time/i), { target: { value: '20:00' } });
      fireEvent.change(screen.getByLabelText(/close date/i), { target: { value: '2024-12-31' } });
      fireEvent.change(screen.getByLabelText(/close time/i), { target: { value: '18:00' } });
      fireEvent.change(screen.getByLabelText(/wheelchair accessible/i), { target: { value: 'no' } });

      fireEvent.click(screen.getByRole('button', { name: /save draft/i }));

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/promotions/shows');
      });
      expect(showsAPI.create).toHaveBeenCalledWith(
        expect.objectContaining({ wheelchair_accessible: 'no' }),
      );
    });
  });

  describe('Movie Rating', () => {
    const cinema: VenueResponse = {
      ...mockVenues[1],
      id: 3,
      name: 'Cinema C',
      venue_type: 'movie_theater',
      default_movie_rating: 'PG-13',
    };

    it('replaces Age Restriction at a movie theater and takes its default', async () => {
      vi.mocked(venuesMyAPI.listMy).mockResolvedValue([...mockVenues, cinema]);
      renderShowForm();
      await waitFor(() => {
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
      });
      expect(screen.getByLabelText(/age restriction/i)).toBeInTheDocument();
      expect(screen.queryByLabelText(/movie rating/i)).not.toBeInTheDocument();

      fireEvent.change(screen.getByRole('combobox', { name: /Venue/ }), { target: { value: '3' } });
      expect(await screen.findByLabelText(/movie rating/i)).toHaveValue('PG-13');
      expect(screen.queryByLabelText(/age restriction/i)).not.toBeInTheDocument();

      fireEvent.change(screen.getByRole('combobox', { name: /Venue/ }), { target: { value: '1' } });
      expect(await screen.findByLabelText(/age restriction/i)).toBeInTheDocument();
    });

    it('sends the movie rating and no age restriction', async () => {
      vi.mocked(venuesMyAPI.listMy).mockResolvedValue([...mockVenues, cinema]);
      vi.mocked(showsAPI.create).mockResolvedValue(
        { id: 1 } as Awaited<ReturnType<typeof showsAPI.create>>,
      );

      renderShowForm();

      await waitFor(() => {
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
      });

      const eventNameInput = screen.getByLabelText(/event name/i);
      eventNameInput.textContent = 'Test Movie';
      fireEvent.input(eventNameInput);
      fireEvent.change(screen.getByLabelText(/genre/i), { target: { value: 'Rock' } });
      fireEvent.change(screen.getByRole('combobox', { name: /Venue/ }), { target: { value: '3' } });
      fireEvent.change(screen.getByLabelText(/show date/i), { target: { value: '2024-12-31' } });
      fireEvent.change(screen.getByLabelText(/show time/i), { target: { value: '20:00' } });
      fireEvent.change(screen.getByLabelText(/close date/i), { target: { value: '2024-12-31' } });
      fireEvent.change(screen.getByLabelText(/close time/i), { target: { value: '18:00' } });
      fireEvent.change(screen.getByLabelText(/movie rating/i), { target: { value: 'R' } });

      fireEvent.click(screen.getByRole('button', { name: /save draft/i }));

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/promotions/shows');
      });
      expect(showsAPI.create).toHaveBeenCalledWith(
        expect.objectContaining({ movie_rating: 'R', age_restriction: null }),
      );
    });
  });
});
