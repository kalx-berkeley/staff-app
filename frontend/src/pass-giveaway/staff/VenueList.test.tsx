import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, fireEvent, within, cleanup } from '@testing-library/react';
import VenueList from './VenueList';
import { venuesAPI } from '../api';
import { renderAndSettle } from '../../test/render';
import type { VenueResponse } from '../types';

vi.mock('../api', () => ({
  venuesAPI: { list: vi.fn() },
}));

const venues = [
  {
    id: 1,
    name: 'The Fox Theater',
    address: '1807 Telegraph Ave',
    owner_details: [
      { name: 'Ana Lopez', email: 'ana@kalx.berkeley.edu' },
      { name: 'Ben Ito', email: 'ben@kalx.berkeley.edu' },
    ],
  },
  { id: 2, name: 'Cornerstone', address: '2367 Shattuck Ave', owner_details: [] },
] as unknown as VenueResponse[];

const rowFor = (venueName: string) => screen.getByText(venueName).closest('tr')!;

describe('staff VenueList', () => {
  beforeEach(() => {
    vi.mocked(venuesAPI.list).mockResolvedValue(venues);
  });

  afterEach(() => {
    cleanup();
  });

  it('lists every rep of a venue, each with a mailto link', async () => {
    await renderAndSettle(<VenueList />);

    const fox = within(rowFor('The Fox Theater'));
    expect(fox.getByText('Ana Lopez')).toBeInTheDocument();
    expect(fox.getByText('Ben Ito')).toBeInTheDocument();
    expect(fox.getByRole('link', { name: 'ben@kalx.berkeley.edu' })).toHaveAttribute(
      'href',
      'mailto:ben@kalx.berkeley.edu',
    );
    expect(within(rowFor('Cornerstone')).getByText('No rep')).toBeInTheDocument();
  });

  it('filters by rep name or email', async () => {
    await renderAndSettle(<VenueList />);
    const search = screen.getByRole('textbox', { name: 'Search venues' });

    fireEvent.change(search, { target: { value: 'ben@' } });
    expect(screen.getByText('The Fox Theater')).toBeInTheDocument();
    expect(screen.queryByText('Cornerstone')).not.toBeInTheDocument();

    fireEvent.change(search, { target: { value: 'nobody' } });
    expect(screen.getByText('No venues match your search.')).toBeInTheDocument();
  });
});
