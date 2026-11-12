/**
 * The show form at a venue that gives staff passes for a different date, where
 * a new show is created as two shows. See
 * docs/pass-giveaway/specs/staff-passes-another-date/plan.md.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ShowForm from './ShowForm';
import { showsAPI, venuesAPI, venuesMyAPI } from '../api';
import type { VenueResponse } from '../types';
import { renderAndSettle } from '../../test/render';

vi.mock('../api', () => ({
  showsAPI: {
    create: vi.fn(),
    createSplit: vi.fn(),
    update: vi.fn(),
    get: vi.fn(),
    publish: vi.fn(),
    listGenres: vi.fn(),
    analyzeDescription: vi.fn(),
    listStaffPassClaimants: vi.fn(),
  },
  venuesAPI: { list: vi.fn() },
  venuesMyAPI: { listMy: vi.fn() },
  promotersAPI: { list: vi.fn().mockResolvedValue([]) },
}));

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const venue = (id: number, name: string, offset: number | null): VenueResponse => ({
  id, name, address: '1 Main St', show_sourcing_instructions: null, pass_call_instructions: null,
  win_frequency_days: null, default_wheelchair_accessible: null, venue_type: 'music',
  default_age_restriction: null, default_movie_rating: null, default_num_pass_pairs: null,
  requires_phone_number: false, email_address_requirement: 'none', requires_email_address: false,
  staff_guest_requires_name: false, hold_close_notifications: false, track_pass_call_in: false,
  default_lottery_enabled: false, default_lottery_window_hours: 24,
  default_dj_preassign_prohibition_days: null, default_close_hours_before_show: null,
  staff_pass_day_offset: offset, default_on_air_description: null,
  default_caller_special_instructions: null, default_staff_instructions: null, has_logo: false,
  show_name_with_logo: false, deleted: false, shows_have_external_promoter: false,
  owner_emails: [], owner_details: [], contacts: [],
});

const venues = [venue(1, 'Normal Hall', null), venue(2, 'Split Club', 1)];

const renderForm = () =>
  renderAndSettle(
    <MemoryRouter initialEntries={['/promotions/shows/new']}>
      <Routes>
        <Route path="/promotions/shows/new" element={<ShowForm />} />
      </Routes>
    </MemoryRouter>
  );

const fillShow = (venueId: string) => {
  const eventName = screen.getByLabelText(/event name/i);
  eventName.textContent = 'Split Night';
  fireEvent.input(eventName);
  fireEvent.change(screen.getByRole('combobox', { name: /Venue/ }), { target: { value: venueId } });
};

const fillOnAirDates = () => {
  fireEvent.change(screen.getByLabelText(/^On-Air Show Date/), { target: { value: '2026-12-04' } });
  fireEvent.change(screen.getByLabelText(/^On-Air Show Time/), { target: { value: '20:00' } });
  fireEvent.change(screen.getByLabelText('Close Date'), { target: { value: '2026-12-02' } });
  fireEvent.change(screen.getByLabelText('Close Time'), { target: { value: '12:00' } });
};

describe('ShowForm at a venue with staff passes for another date', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(venuesAPI.list).mockResolvedValue(venues);
    vi.mocked(venuesMyAPI.listMy).mockResolvedValue(venues);
    vi.mocked(showsAPI.listGenres).mockResolvedValue([]);
  });

  it('says nothing about two shows at a normal venue', async () => {
    await renderForm();
    fillShow('1');

    expect(screen.queryByText('Saving creates two shows')).not.toBeInTheDocument();
    expect(screen.getByLabelText(/^Show Date/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save Draft' })).toBeInTheDocument();
  });

  it('explains the two shows, following the on-air dates', async () => {
    await renderForm();
    fillShow('2');
    fillOnAirDates();

    const box = screen.getByRole('region', { name: 'Saving creates two shows' });
    expect(box).toHaveTextContent('Split Club gives us staff passes for a different night');
    expect(box).toHaveTextContent('usually 1 day after');
    expect(box).toHaveTextContent(
      'On-air show, Fri, Dec 4, 2026 at 8:00 PM: 1 pass pair for on-air giveaways and no staff passes. Closes Wed, Dec 2, 2026 at 12:00 PM.'
    );
    expect(box).toHaveTextContent(
      'Staff show, Sat, Dec 5, 2026 at 8:00 PM: 1 staff pass and no pass pairs. Closes Thu, Dec 3, 2026 at 12:00 PM.'
    );
    expect(within(box).getByLabelText('Staff Show Date')).toHaveValue('12/05/2026');
    expect(screen.getByRole('button', { name: 'Save 2 Drafts' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Publish 2 Shows' })).toBeInTheDocument();
  });

  it('creates and publishes both shows, with a changed staff show date', async () => {
    vi.mocked(showsAPI.createSplit).mockResolvedValue({
      on_air_show: { id: 41 },
      staff_show: { id: 42 },
    } as Awaited<ReturnType<typeof showsAPI.createSplit>>);
    vi.mocked(showsAPI.publish).mockResolvedValue(
      {} as Awaited<ReturnType<typeof showsAPI.publish>>,
    );
    await renderForm();
    fillShow('2');
    fillOnAirDates();
    fireEvent.change(screen.getByLabelText('Staff Show Date'), { target: { value: '2026-12-06' } });

    // The staff show's close moves with its date until it's changed
    expect(screen.getByLabelText('Staff Show Close Date')).toHaveValue('12/04/2026');

    fireEvent.click(screen.getByRole('button', { name: 'Publish 2 Shows' }));

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/promotions/shows/41');
    });
    expect(showsAPI.create).not.toHaveBeenCalled();
    expect(showsAPI.createSplit).toHaveBeenCalledWith(
      expect.objectContaining({
        show_date: '2026-12-04',
        show_time: '20:00',
        num_pass_pairs: 1,
        staff_show_date: '2026-12-06',
        staff_show_time: '20:00',
        staff_planned_close_date: '2026-12-04',
        staff_planned_close_time: '12:00',
      })
    );
    expect(showsAPI.publish).toHaveBeenCalledWith(41);
    expect(showsAPI.publish).toHaveBeenCalledWith(42);
  });

  it("won't save a staff show that closes after it starts", async () => {
    await renderForm();
    fillShow('2');
    fillOnAirDates();
    fireEvent.change(screen.getByLabelText('Staff Show Close Date'), {
      target: { value: '2026-12-06' },
    });

    fireEvent.click(screen.getByRole('button', { name: 'Save 2 Drafts' }));

    expect(
      await screen.findByText("The staff show's planned close must be before the staff show")
    ).toBeInTheDocument();
    expect(showsAPI.createSplit).not.toHaveBeenCalled();
  });

  it("doesn't split a multi-day show", async () => {
    await renderForm();
    fillShow('2');
    fireEvent.click(screen.getByRole('button', { name: 'Multi-Day' }));

    expect(screen.queryByText('Saving creates two shows')).not.toBeInTheDocument();
    expect(screen.getByText(/multi-day shows aren't split/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save Draft' })).toBeInTheDocument();
  });
});
