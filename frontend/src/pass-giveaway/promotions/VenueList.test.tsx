import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, fireEvent, cleanup } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation, useNavigate } from 'react-router-dom';
import { useReturnToList } from '../listUrlState';
import VenueList from './VenueList';
import { venuesAPI, venuesMyAPI } from '../api';
import { renderAndSettle } from '../../test/render';
import type { VenueResponse } from '../types';

vi.mock('../api', () => ({
  venuesAPI: { list: vi.fn() },
  venuesMyAPI: { listMy: vi.fn() },
}));

const venues = [
  { id: 7, name: 'The Fox Theater', address: '1807 Telegraph Ave', owner_details: [] },
  { id: 8, name: 'Cornerstone', address: '2367 Shattuck Ave', owner_details: [] },
] as unknown as VenueResponse[];

const ShowsPage = () => {
  const location = useLocation();
  return <div data-testid="shows-page">{location.pathname + location.search}</div>;
};

// Stands in for VenueEdit: its Back button and the browser's Back.
const EditPage = () => {
  const navigate = useNavigate();
  const returnTo = useReturnToList('/promotions/venues');
  return (
    <>
      <button onClick={() => navigate(returnTo)}>Back to Venues</button>
      <button onClick={() => navigate(-1)}>Browser Back</button>
    </>
  );
};

const renderList = () =>
  renderAndSettle(
    <MemoryRouter initialEntries={['/promotions/venues']}>
      <Routes>
        <Route path="/promotions/venues" element={<VenueList />} />
        <Route path="/staff/shows" element={<ShowsPage />} />
        <Route path="/promotions/venues/:id/edit" element={<EditPage />} />
      </Routes>
    </MemoryRouter>,
  );

describe('promotions VenueList', () => {
  beforeEach(() => {
    vi.mocked(venuesMyAPI.listMy).mockResolvedValue(venues);
    vi.mocked(venuesAPI.list).mockResolvedValue(venues);
  });

  afterEach(() => {
    cleanup();
    localStorage.clear();
  });

  it.each(['card', 'compact'])(
    "Shows opens the staff shows page filtered to the venue (%s view)",
    async (mode) => {
      localStorage.setItem('kalx_venue_view_mode', mode);
      await renderList();

      fireEvent.click(screen.getAllByRole('button', { name: 'Shows' })[0]);

      expect(await screen.findByTestId('shows-page')).toHaveTextContent('/staff/shows?venue=7');
    },
  );

  it.each(['Back to Venues', 'Browser Back'])(
    'keeps the filter and All Venues after editing a venue and going back (%s)',
    async (back) => {
      await renderList();
      fireEvent.click(screen.getByRole('button', { name: 'All Venues' }));
      await screen.findByText('Cornerstone');
      fireEvent.change(screen.getByPlaceholderText(/Filter by venue/), {
        target: { value: 'fox' },
      });
      expect(screen.queryByText('Cornerstone')).not.toBeInTheDocument();

      fireEvent.click(screen.getByRole('button', { name: 'Edit' }));
      fireEvent.click(await screen.findByRole('button', { name: back }));

      expect(await screen.findByText('The Fox Theater')).toBeInTheDocument();
      expect(screen.queryByText('Cornerstone')).not.toBeInTheDocument();
      expect(screen.getByPlaceholderText(/Filter by venue/)).toHaveValue('fox');
      expect(screen.getByRole('button', { name: 'All Venues' })).toHaveClass('btn-primary');
      expect(venuesAPI.list).toHaveBeenCalledTimes(2);
    },
  );
});
