import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ShowForm from './ShowForm';
import { showsAPI, venuesAPI, venuesMyAPI } from '../../services/api';
import type { VenueResponse } from '../../types';

// Mock the API
vi.mock('../../services/api', () => ({
  showsAPI: {
    create: vi.fn(),
    update: vi.fn(),
    get: vi.fn(),
    publish: vi.fn(),
    listGenres: vi.fn(),
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
    { id: 1, name: 'Venue A', address: '123 Main St', pass_call_instructions: null, win_frequency_days: null, default_wheelchair_accessible: null, default_age_restriction: null, default_num_pass_pairs: null, requires_phone_number: false, requires_email_address: false, staff_guest_requires_name: false, default_lottery_enabled: false, default_lottery_window_hours: 24, default_dj_preassign_prohibition_days: null, default_close_hours_before_show: null, has_logo: false, deleted: false, shows_have_external_promoter: false, owner_emails: [], contacts: [] },
    { id: 2, name: 'Venue B', address: '456 Oak Ave', pass_call_instructions: null, win_frequency_days: null, default_wheelchair_accessible: null, default_age_restriction: null, default_num_pass_pairs: null, requires_phone_number: false, requires_email_address: false, staff_guest_requires_name: false, default_lottery_enabled: false, default_lottery_window_hours: 24, default_dj_preassign_prohibition_days: null, default_close_hours_before_show: null, has_logo: false, deleted: false, shows_have_external_promoter: false, owner_emails: [], contacts: [] },
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
        wheelchair_accessible: true,
        num_pass_pairs: 1,
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
});
