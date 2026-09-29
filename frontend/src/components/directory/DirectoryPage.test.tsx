import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, within, cleanup, fireEvent } from '@testing-library/react';
import App from '../../App';
import { AuthProvider } from '../../contexts/AuthContext';
import { directoryAPI, usersAPI } from '../../services/api';
import type { DirectoryEntry, UserResponse } from '../../types';

vi.mock('../../services/api', () => ({
  AUTH_DIAG_KEY: 'kalx_auth_diag',
  usersAPI: { getMe: vi.fn() },
  directoryAPI: {
    list: vi.fn(),
    photoUrl: vi.fn(() => null),
  },
  handleAPIError: vi.fn(),
}));

const entry = (overrides: Partial<DirectoryEntry>): DirectoryEntry => ({
  id: 0,
  name: '',
  pronouns: null,
  email: '',
  phone: '',
  dj_name: null,
  dj_personas: [],
  departments: [],
  statuses: ['Active'],
  titles_and_roles: null,
  photo_version: null,
  ...overrides,
});

const ENTRIES: DirectoryEntry[] = [
  entry({
    id: 1,
    name: 'Amy Adams',
    email: 'amy@example.com',
    phone: '510-555-0001',
    departments: ['Music'],
  }),
  entry({
    id: 2,
    name: 'Bea Brown',
    pronouns: 'she/her',
    email: 'bea@example.com',
    phone: '(510) 642-1111',
    dj_name: 'DJ Bea, Bea, Esq.',
    dj_personas: [
      { id: 42, name: 'DJ Bea' },
      { id: 43, name: 'Bea, Esq.' },
    ],
    departments: ['News'],
    statuses: ['Active', 'Paid Staff'],
    titles_and_roles: 'News Director\nOffice hours: Tue 2-4',
  }),
  entry({
    id: 3,
    name: 'Cal Chen',
    email: 'cal@example.com',
    phone: '510-555-0003',
    departments: ['Music', 'News'],
  }),
];

const staffUser: UserResponse = {
  email: 'amy@example.com',
  role: 'staff',
  is_dj_network: false,
  is_station_office_network: false,
  profile: { id: 1, name: 'Amy Adams', phone: '510-555-0001', dj_name: null, is_sublist_dj: false },
};

const renderDirectory = async (path = '/directory') => {
  window.history.pushState({}, '', path);
  vi.mocked(usersAPI.getMe).mockResolvedValue(staffUser);
  vi.mocked(directoryAPI.list).mockResolvedValue(ENTRIES);
  render(
    <AuthProvider>
      <App />
    </AuthProvider>,
  );
  await screen.findByRole('table');
};

const names = () =>
  within(screen.getByRole('table'))
    .queryAllByRole('link')
    .filter((link) => link.classList.contains('directory-name'))
    .map((link) => link.textContent);

describe('DirectoryPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('lists every staff member sorted by name, with contact links', async () => {
    await renderDirectory();

    expect(names()).toEqual(['Amy Adams', 'Bea Brown', 'Cal Chen']);
    expect(screen.getByRole('status')).toHaveTextContent('3 staff');
    expect(screen.getByRole('link', { name: 'bea@example.com' })).toHaveAttribute(
      'href',
      'mailto:bea@example.com',
    );
    expect(screen.getByRole('link', { name: '(510) 642-1111' })).toHaveAttribute(
      'href',
      'tel:(510) 642-1111',
    );
    expect(screen.getByRole('link', { name: 'DJ Bea' })).toHaveAttribute(
      'href',
      'https://spinitron.com/KALX/dj/42/',
    );
    expect(screen.getByRole('link', { name: 'Bea, Esq.' })).toHaveAttribute(
      'href',
      'https://spinitron.com/KALX/dj/43/',
    );
    expect(document.title).toBe('KALX Staff Directory');
  });

  it('searches, including by phone digits and titles, and keeps the query in the URL', async () => {
    await renderDirectory();
    const search = screen.getByRole('searchbox', { name: /search the staff directory/i });

    fireEvent.change(search, { target: { value: '642 1111' } });
    await waitFor(() => expect(names()).toEqual(['Bea Brown']));
    expect(window.location.search).toBe('?q=642+1111');

    fireEvent.change(search, { target: { value: 'office hours' } });
    await waitFor(() => expect(names()).toEqual(['Bea Brown']));
    expect(screen.getByRole('status')).toHaveTextContent('1 of 3 staff');
  });

  it('filters by department from the URL and the filter menu', async () => {
    await renderDirectory('/directory?dept=News');

    expect(names()).toEqual(['Bea Brown', 'Cal Chen']);

    fireEvent.click(screen.getByRole('checkbox', { name: 'Music' }));
    await waitFor(() => expect(names()).toEqual(['Amy Adams', 'Bea Brown', 'Cal Chen']));
    expect(new URLSearchParams(window.location.search).getAll('dept')).toEqual(['News', 'Music']);

    fireEvent.click(screen.getByRole('button', { name: 'Clear all' }));
    await waitFor(() => expect(window.location.search).toBe(''));
  });

  it('filters by status', async () => {
    await renderDirectory('/directory?status=Paid+Staff');

    expect(names()).toEqual(['Bea Brown']);
  });

  it('filters on a department or status tag when it is clicked', async () => {
    await renderDirectory('/directory?q=b&status=Active');
    const row = screen.getByRole('link', { name: 'Bea Brown' }).closest('tr')!;

    const newsTag = within(row).getByRole('link', { name: 'News' });
    expect(newsTag).toHaveAttribute('href', '/directory?q=b&dept=News&status=Active');
    fireEvent.click(newsTag);
    await waitFor(() => expect(window.location.search).toBe('?q=b&dept=News&status=Active'));
    expect(window.location.pathname).toBe('/directory');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    fireEvent.click(within(row).getByRole('link', { name: 'Paid Staff' }));
    await waitFor(() => expect(window.location.search).toBe('?q=b&dept=News&status=Paid+Staff'));
    expect(names()).toEqual(['Bea Brown']);
  });

  it('sorts by a column header, keeping the sort in the URL', async () => {
    await renderDirectory();

    fireEvent.click(screen.getByRole('button', { name: /^Name/ }));

    await waitFor(() => expect(names()).toEqual(['Cal Chen', 'Bea Brown', 'Amy Adams']));
    expect(window.location.search).toBe('?sort=-name');
    expect(screen.getByRole('columnheader', { name: /^Name/ })).toHaveAttribute(
      'aria-sort',
      'descending',
    );
  });

  it('opens a shareable detail panel with Titles and Roles, and closes it', async () => {
    await renderDirectory('/directory?q=bea');

    fireEvent.click(screen.getByText('she/her'));

    const panel = await screen.findByRole('dialog', { name: /Bea Brown/ });
    expect(window.location.pathname).toBe('/directory/2');
    expect(window.location.search).toBe('?q=bea');
    expect(within(panel).getByText(/Office hours: Tue 2-4/)).toBeInTheDocument();
    expect(within(panel).getByRole('link', { name: 'DJ Bea' })).toHaveAttribute(
      'href',
      'https://spinitron.com/KALX/dj/42/',
    );
    expect(within(panel).getByRole('link', { name: 'Bea, Esq.' })).toHaveAttribute(
      'href',
      'https://spinitron.com/KALX/dj/43/',
    );
    expect(document.title).toBe('Bea Brown · KALX Staff Directory');

    fireEvent.keyDown(document, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(window.location.pathname).toBe('/directory');
    expect(window.location.search).toBe('?q=bea');
  });

  it('links to your own record', async () => {
    await renderDirectory('/directory/1');

    const panel = await screen.findByRole('dialog', { name: /Amy Adams/ });
    expect(within(panel).getByText('You')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'My record' })).toHaveAttribute('href', '/directory/1');
  });

  it('says so when a linked person is not in the directory', async () => {
    await renderDirectory('/directory/99');

    expect(await screen.findByRole('dialog')).toHaveTextContent("isn't in the staff directory");
  });
});
