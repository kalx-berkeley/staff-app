import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';
import { renderAndSettle } from '../../test/render';
import ShowInfoCards from './ShowInfoCards';
import type { ShowResponse } from '../types';

const baseShow: ShowResponse = {
  id: 1,
  event_name: 'Test Concert',
  genre: ['Rock'],
  venue: { id: 1, name: 'Test Venue', address: '123 Main St', show_sourcing_instructions: null, pass_call_instructions: null, win_frequency_days: null, default_wheelchair_accessible: null, venue_type: 'music', default_age_restriction: null, default_movie_rating: null, default_num_pass_pairs: null, requires_phone_number: false, email_address_requirement: 'none', requires_email_address: false, staff_guest_requires_name: false, hold_close_notifications: false, default_lottery_enabled: false, default_lottery_window_hours: 24, default_dj_preassign_prohibition_days: null, default_close_hours_before_show: null, default_on_air_description: null, default_caller_special_instructions: null, default_staff_instructions: null, has_logo: false, show_name_with_logo: false, deleted: false, shows_have_external_promoter: false, owner_emails: [], owner_details: [], contacts: [] },
  show_date: '2024-12-31',
  show_time: '20:00',
  show_start_date: null,
  on_air_description: null,
  caller_special_instructions: null,
  staff_instructions: null,
  age_restriction: '21+',
  movie_rating: null,
  wheelchair_accessible: 'yes',
  num_pass_pairs: 2,
  staff_pass_adjustment: 0,
  num_staff_passes: 2,
  num_tabler_passes: 0,
  available_tabler_count: 0,
  tablers: [],
  promotions_contacts: [],
  guest_list_requirements: { requires_phone_number: false, email_address_requirement: 'none', requires_email_address: false, staff_guest_requires_name: false },
  attempts: [],
  status: 'published',
  passes: [],
  available_pair_count: 0,
  available_staff_count: 1,
  planned_close_date: null,
  planned_close_time: null,
  auto_close: false,
  close_notifications_pending: false,
  close_notifications_sent_at: null,
  close_notifications_sent_by: null,
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
};

describe('ShowInfoCards', () => {
  it('shows the details as labelled fields, with genres as tags', async () => {
    await renderAndSettle(
      <ShowInfoCards show={{ ...baseShow, genre: ['Rock', 'Punk'] }} />,
    );

    expect(screen.getByRole('heading', { name: 'Show Information' })).toBeInTheDocument();
    expect(screen.getByText('Genres')).toBeInTheDocument();
    expect(screen.getByText('Rock')).toHaveClass('detail-tag');
    expect(screen.getByText('Punk')).toHaveClass('detail-tag');
    expect(screen.getByText('Test Venue')).toHaveTextContent('123 Main St');
    expect(screen.getByText('8:00 PM')).toBeInTheDocument();
    expect(screen.getByText('21+')).toBeInTheDocument();
  });

  it('says "None" when the show has no genre', async () => {
    await renderAndSettle(<ShowInfoCards show={{ ...baseShow, genre: [] }} />);

    expect(screen.getByText('None')).toHaveClass('detail-empty');
  });

  it('shows the planned close when the show has one', async () => {
    const show = { ...baseShow, planned_close_date: '2024-12-30', planned_close_time: '12:00', auto_close: true };
    await renderAndSettle(<ShowInfoCards show={show} />);

    expect(screen.getByText('Planned Close')).toBeInTheDocument();
    expect(screen.getByText(/12:00 PM · auto-close enabled/)).toBeInTheDocument();
  });

  it('leaves out the planned close when the show has none', async () => {
    await renderAndSettle(<ShowInfoCards show={baseShow} />);

    expect(screen.queryByText('Planned Close')).not.toBeInTheDocument();
  });

  it('lists the promotions reps with phone and email links', async () => {
    await renderAndSettle(
      <ShowInfoCards
        show={{ ...baseShow, promotions_contacts: [{ name: 'Pat Rep', email: 'pat@example.com', phone: '5105551234' }] }}
       
      />,
    );

    expect(screen.getByRole('heading', { name: 'KALX Promotions Rep' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'pat@example.com' })).toHaveAttribute('href', 'mailto:pat@example.com');
    expect(screen.getByRole('link', { name: '(510) 555-1234' })).toHaveAttribute('href', 'tel:5105551234');
  });

  it('uses one column when there are no promotions reps', async () => {
    const { container } = await renderAndSettle(<ShowInfoCards show={baseShow} />);

    expect(container.querySelector('.show-info')).toHaveClass('show-info--single');
    expect(screen.queryByText(/KALX Promotions Rep/)).not.toBeInTheDocument();
  });
});
