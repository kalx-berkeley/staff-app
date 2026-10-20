import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, fireEvent, within, cleanup, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import SpecialtyShowList from './SpecialtyShowList';
import { specialtyShowsAPI } from '../api';
import { renderAndSettle } from '../../test/render';
import type { SpecialtyShowResponse } from '../types';

vi.mock('../api', () => ({
  specialtyShowsAPI: {
    list: vi.fn(),
    create: vi.fn(),
    delete: vi.fn(),
    setRetired: vi.fn(),
    getUpcomingTitles: vi.fn().mockResolvedValue([]),
    listMine: vi.fn().mockResolvedValue([]),
  },
}));

vi.mock('../../common/contexts/authHooks', () => ({
  useAuth: () => ({ user: { role: 'promotions', email: 'promo@example.com' } }),
}));

const show = (overrides: Partial<SpecialtyShowResponse>): SpecialtyShowResponse => ({
  id: 1,
  name: 'Take Five',
  deleted: false,
  retired: false,
  spinitron_shows: [
    { id: 301137, title: 'Take Five', url: 'https://spinitron.com/KALX/show/301137/' },
  ],
  owner_emails: [],
  owner_details: [],
  dj_names: [],
  ...overrides,
});

const renderList = () =>
  renderAndSettle(
    <MemoryRouter>
      <SpecialtyShowList />
    </MemoryRouter>,
  );

describe('SpecialtyShowList', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('lists retired shows separately and warns about shows without a Spinitron link', async () => {
    vi.mocked(specialtyShowsAPI.list).mockResolvedValue([
      show({}),
      show({ id: 2, name: 'Legacy Hour', spinitron_shows: [] }),
      show({ id: 3, name: 'Old Show', retired: true }),
    ]);
    await renderList();

    expect(specialtyShowsAPI.list).toHaveBeenCalledWith(true);
    expect(screen.getByRole('alert')).toHaveTextContent(
      "don't have a Spinitron link yet, so their playlists count as regular DJ shifts for the DJ sublist: Legacy Hour.",
    );
    expect(screen.getByRole('heading', { name: 'Take Five' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Old Show' })).not.toBeInTheDocument();
    const retired = screen.getByText('Retired shows (1)').closest('details')!;
    expect(within(retired).getByRole('link', { name: 'Old Show' })).toBeInTheDocument();
  });

  it('retires and un-retires shows', async () => {
    vi.mocked(specialtyShowsAPI.list).mockResolvedValue([
      show({}),
      show({ id: 3, name: 'Old Show', retired: true }),
    ]);
    vi.mocked(specialtyShowsAPI.setRetired).mockResolvedValue(show({ retired: true }));
    await renderList();

    fireEvent.click(screen.getAllByRole('button', { name: 'Retire' })[0]);
    await waitFor(() => expect(specialtyShowsAPI.list).toHaveBeenCalledTimes(2));
    expect(specialtyShowsAPI.setRetired).toHaveBeenCalledWith(1, true);

    fireEvent.click(screen.getByRole('button', { name: 'Un-retire' }));
    await waitFor(() => expect(specialtyShowsAPI.list).toHaveBeenCalledTimes(3));
    expect(specialtyShowsAPI.setRetired).toHaveBeenCalledWith(3, false);
    await screen.findByRole('heading', { name: 'Take Five' });
  });

  it('needs a Spinitron link to add a show', async () => {
    vi.mocked(specialtyShowsAPI.list).mockResolvedValue([]);
    vi.mocked(specialtyShowsAPI.create).mockRejectedValue({ detail: 'Spinitron has no show' });
    await renderList();

    fireEvent.change(screen.getByPlaceholderText('New specialty show name...'), {
      target: { value: 'Night Moves' },
    });
    const add = screen.getByRole('button', { name: 'Add' });
    expect(add).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Spinitron show or playlist link'), {
      target: { value: 'https://spinitron.com/KALX/show/999/' },
    });
    fireEvent.click(add);

    expect(await screen.findByText('Spinitron has no show')).toBeInTheDocument();
    expect(specialtyShowsAPI.create).toHaveBeenCalledWith({
      name: 'Night Moves',
      spinitron_urls: ['https://spinitron.com/KALX/show/999/'],
    });
  });
});
