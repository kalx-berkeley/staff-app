import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, fireEvent, cleanup, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import SpecialtyShowDetail, { TalkShowDetail } from './SpecialtyShowDetail';
import { specialtyShowsAPI } from '../api';
import { renderAndSettle } from '../../test/render';
import type { Identity, SpecialtyShowResponse } from '../types';

vi.mock('../api', () => ({
  specialtyShowsAPI: {
    get: vi.fn(),
    update: vi.fn(),
    listStaffEmails: vi.fn(),
    getDjHistory: vi.fn(),
    getDjOptions: vi.fn(),
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
  djs: [],
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
    vi.mocked(specialtyShowsAPI.getDjOptions).mockResolvedValue([]);
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
    expect(specialtyShowsAPI.getDjOptions).not.toHaveBeenCalled();

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

  describe('a music show’s DJs', () => {
    const persona = (persona_id: number, name: string, staff_name: string): Identity => ({
      name,
      kind: 'persona',
      persona_id,
      specialty_show_id: null,
      staff_name,
    });
    const musicShow: SpecialtyShowResponse = {
      ...talkShow,
      id: 3,
      name: 'Take Five',
      category: 'music',
      staff_member_emails: [],
      staff_member_details: [],
      djs: [
        { persona_id: 11, name: 'DJ Wolfman' },
        { persona_id: null, name: 'Old Typed Name' },
      ],
    };

    beforeEach(() => {
      vi.mocked(specialtyShowsAPI.get).mockResolvedValue(musicShow);
      vi.mocked(specialtyShowsAPI.update).mockResolvedValue(musicShow);
      vi.mocked(specialtyShowsAPI.getDjOptions).mockResolvedValue([
        persona(11, 'DJ Wolfman', 'Wolf'),
        persona(12, 'Nightowl', 'Owl Person'),
        persona(13, 'Lark', 'Lark Person'),
      ]);
    });

    it('adds a staff member’s persona picked by name or by its holder', async () => {
      await renderAt('/staff/specialty-shows/3');
      expect(specialtyShowsAPI.getDjOptions).toHaveBeenCalledWith(3);

      fireEvent.change(screen.getByPlaceholderText('DJ name'), { target: { value: 'owl per' } });
      fireEvent.mouseDown(await screen.findByText('Nightowl'));
      fireEvent.click(screen.getByRole('button', { name: 'Add DJ' }));

      expect(await screen.findByText('DJ added.')).toBeInTheDocument();
      expect(specialtyShowsAPI.update).toHaveBeenCalledWith(3, { dj_persona_ids: [11, 12] });
    });

    it('can’t add a typed name that isn’t a staff persona', async () => {
      await renderAt('/staff/specialty-shows/3');

      fireEvent.change(screen.getByPlaceholderText('DJ name'), { target: { value: 'Somebody' } });

      expect(screen.getByRole('button', { name: 'Add DJ' })).toBeDisabled();
    });

    it('removes a DJ by persona, and keeps a DJ with no persona', async () => {
      await renderAt('/staff/specialty-shows/3');

      expect(screen.getByText('(not linked to a Spinitron persona yet)')).toBeInTheDocument();
      const removes = screen.getAllByRole('button', { name: 'Remove' });
      fireEvent.click(removes[removes.length - 1]);

      await waitFor(() =>
        expect(specialtyShowsAPI.update).toHaveBeenCalledWith(3, { dj_persona_ids: [] }),
      );
      expect(await screen.findByText('DJ removed.')).toBeInTheDocument();
    });

    it('suggests recent hosts who are staff personas', async () => {
      vi.mocked(specialtyShowsAPI.getDjHistory).mockResolvedValue(['lark', 'DJ Wolfman', 'Guest']);
      await renderAt('/staff/specialty-shows/3');

      fireEvent.click(await screen.findByRole('button', { name: '+ Lark' }));

      expect(await screen.findByText('DJ added.')).toBeInTheDocument();
      expect(specialtyShowsAPI.update).toHaveBeenCalledWith(3, { dj_persona_ids: [11, 13] });
      expect(screen.queryByRole('button', { name: '+ Guest' })).not.toBeInTheDocument();
    });
  });
});
