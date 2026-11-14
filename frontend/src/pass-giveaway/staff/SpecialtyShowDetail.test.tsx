import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, fireEvent, cleanup } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import SpecialtyShowDetail, { TalkShowDetail } from './SpecialtyShowDetail';
import { specialtyShowsAPI, autocompleteAPI } from '../api';
import { renderAndSettle } from '../../test/render';
import type { SpecialtyShowResponse } from '../types';

vi.mock('../api', () => ({
  specialtyShowsAPI: {
    get: vi.fn(),
    update: vi.fn(),
    listStaffEmails: vi.fn(),
    getDjHistory: vi.fn(),
  },
  autocompleteAPI: {
    getDJNames: vi.fn(),
  },
}));

vi.mock('../../common/contexts/authHooks', () => ({
  useAuth: () => ({ user: { role: 'promotions', email: 'promo@example.com' } }),
}));

const talkShow: SpecialtyShowResponse = {
  id: 7,
  name: 'Morning Report',
  category: 'talk',
  deleted: false,
  retired: false,
  spinitron_shows: [{ id: 555, title: 'Morning Report', url: 'https://spinitron.com/KALX/show/555/' }],
  owner_emails: [],
  owner_details: [],
  dj_names: [],
  staff_member_emails: ['news@example.com'],
  staff_member_details: [{ email: 'news@example.com', name: 'Nia News' }],
};

const renderAt = (path: string) =>
  renderAndSettle(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/staff/specialty-shows/:id" element={<SpecialtyShowDetail />} />
        <Route path="/staff/talk-shows/:id" element={<TalkShowDetail />} />
      </Routes>
    </MemoryRouter>,
  );

describe('SpecialtyShowDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(specialtyShowsAPI.get).mockResolvedValue(talkShow);
    vi.mocked(specialtyShowsAPI.listStaffEmails).mockResolvedValue([
      { email: 'news@example.com', name: 'Nia News' },
      { email: 'sam@example.com', name: 'Sam Sports' },
    ]);
    vi.mocked(specialtyShowsAPI.getDjHistory).mockResolvedValue([]);
    vi.mocked(autocompleteAPI.getDJNames).mockResolvedValue([]);
  });

  afterEach(() => {
    cleanup();
  });

  it('lists a talk show’s staff members instead of DJs, and adds one', async () => {
    vi.mocked(specialtyShowsAPI.update).mockResolvedValue(talkShow);
    await renderAt('/staff/talk-shows/7');

    expect(screen.getByRole('heading', { name: 'Staff Members' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'DJs' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Nia News' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '← Back to Talk & Info Shows' })).toBeInTheDocument();
    expect(autocompleteAPI.getDJNames).not.toHaveBeenCalled();

    const inputs = screen.getAllByPlaceholderText('Staff name or email address');
    fireEvent.change(inputs[inputs.length - 1], { target: { value: 'sam@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add Staff Member' }));

    expect(await screen.findByText('Staff member added.')).toBeInTheDocument();
    expect(specialtyShowsAPI.update).toHaveBeenCalledWith(7, {
      staff_member_emails: ['news@example.com', 'sam@example.com'],
    });
  });

  it('sends a talk show opened as a music show to its own page', async () => {
    await renderAt('/staff/specialty-shows/7');

    expect(await screen.findByRole('heading', { name: 'Staff Members' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '← Back to Talk & Info Shows' })).toBeInTheDocument();
  });
});
