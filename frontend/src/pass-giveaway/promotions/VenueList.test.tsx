import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, fireEvent, cleanup } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
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
] as unknown as VenueResponse[];

const ShowsPage = () => {
  const location = useLocation();
  return <div data-testid="shows-page">{location.pathname + location.search}</div>;
};

const renderList = () =>
  renderAndSettle(
    <MemoryRouter initialEntries={['/promotions/venues']}>
      <Routes>
        <Route path="/promotions/venues" element={<VenueList />} />
        <Route path="/staff/shows" element={<ShowsPage />} />
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

      fireEvent.click(screen.getByRole('button', { name: 'Shows' }));

      expect(await screen.findByTestId('shows-page')).toHaveTextContent('/staff/shows?venue=7');
    },
  );
});
