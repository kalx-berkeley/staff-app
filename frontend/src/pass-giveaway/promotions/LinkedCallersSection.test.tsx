import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { callersAPI } from '../api';
import { renderAndSettle } from '../../test/render';
import type { CallerPhone, CallerSuggestion, LinkedCaller } from '../types';
import LinkedCallersSection from './LinkedCallersSection';

vi.mock('../api', () => ({
  callersAPI: {
    getSuggestions: vi.fn(),
    list: vi.fn(),
    getCommonNames: vi.fn(),
    search: vi.fn(),
    preview: vi.fn(),
    link: vi.fn(),
    updateNote: vi.fn(),
    unlinkPhone: vi.fn(),
    unlink: vi.fn(),
    dismiss: vi.fn(),
    undoDismissal: vi.fn(),
    markCommon: vi.fn(),
    unmarkCommon: vi.fn(),
  },
}));

const phone = (number: string, overrides: Partial<CallerPhone> = {}): CallerPhone => ({
  phone: number,
  names: ['John Doe'],
  wins: 1,
  last_won_at: '2026-06-10T20:00:00Z',
  caller_id: null,
  ...overrides,
});

const suggestion = (overrides: Partial<CallerSuggestion> = {}): CallerSuggestion => ({
  key: 'john doe',
  name: 'John Doe',
  spellings: ['John Doe', 'Jon Doe'],
  status: 'unreviewed',
  status_label: 'Unreviewed',
  flagged: true,
  common_names: [],
  phones: [phone('2125555555'), phone('2128888888')],
  wins: [
    {
      pass_id: 1,
      won_at: '2026-06-10T20:00:00Z',
      name: 'John Doe',
      phone: '2128888888',
      email: null,
      show_id: 7,
      show: 'The Chainsmokers',
      show_date: '2026-06-17',
      venue: 'The Greek Theater',
    },
  ],
  ...overrides,
});

const caller = (overrides: Partial<LinkedCaller> = {}): LinkedCaller => ({
  id: 4,
  note: 'Same voice',
  created_at: '2026-06-11T20:00:00Z',
  updated_at: '2026-06-11T20:00:00Z',
  phones: [phone('2125555555', { caller_id: 4 }), phone('2128888888', { caller_id: 4, wins: 0 })],
  ...overrides,
});

const renderSection = (url = '/admin') =>
  renderAndSettle(
    <MemoryRouter initialEntries={[url]}>
      <LinkedCallersSection />
    </MemoryRouter>
  );

describe('LinkedCallersSection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(callersAPI.getSuggestions).mockResolvedValue([suggestion()]);
    vi.mocked(callersAPI.list).mockResolvedValue([]);
    vi.mocked(callersAPI.getCommonNames).mockResolvedValue([]);
  });

  it('lists unresolved suggestions, flagged ones marked', async () => {
    await renderSection();

    expect(callersAPI.getSuggestions).toHaveBeenCalledWith(false, undefined);
    expect(screen.getByText('John Doe', { selector: 'strong' })).toBeInTheDocument();
    expect(screen.getByText("Would have broken a venue's limit")).toBeInTheDocument();
    expect(screen.getByText('Spellings: John Doe, Jon Doe')).toBeInTheDocument();
    expect(screen.getByText('(212) 555-5555')).toBeInTheDocument();
  });

  it('links the checked numbers after confirming, with a note', async () => {
    vi.mocked(callersAPI.preview).mockResolvedValue({
      phones: ['2125555555', '2128888888'],
      caller_ids: [],
      already_linked: false,
    });
    vi.mocked(callersAPI.link).mockResolvedValue(caller());
    await renderSection();

    fireEvent.click(screen.getByRole('button', { name: 'Link checked numbers' }));
    const dialog = await screen.findByRole('dialog', { name: 'Confirm linking' });
    expect(callersAPI.preview).toHaveBeenCalledWith(['2125555555', '2128888888']);
    expect(within(dialog).getByText('(212) 888-8888')).toBeInTheDocument();

    fireEvent.change(within(dialog).getByLabelText('Note (optional)'), {
      target: { value: 'Same email' },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Link these numbers' }));

    await waitFor(() =>
      expect(callersAPI.link).toHaveBeenCalledWith(['2125555555', '2128888888'], 'Same email')
    );
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(callersAPI.getSuggestions).toHaveBeenCalledTimes(2);
  });

  it('says when linking merges callers', async () => {
    vi.mocked(callersAPI.preview).mockResolvedValue({
      phones: ['1', '2', '3'],
      caller_ids: [1, 2],
      already_linked: false,
    });
    await renderSection();

    fireEvent.click(screen.getByRole('button', { name: 'Link checked numbers' }));
    expect(await screen.findByText(/This merges 2 linked callers/)).toBeInTheDocument();
  });

  it('needs two checked numbers to link', async () => {
    await renderSection();

    fireEvent.click(screen.getByLabelText(/\(212\) 555-5555/));
    expect(screen.getByRole('button', { name: 'Link checked numbers' })).toBeDisabled();
  });

  it('dismisses a group and marks a name too common', async () => {
    vi.mocked(callersAPI.dismiss).mockResolvedValue();
    vi.mocked(callersAPI.markCommon).mockResolvedValue();
    await renderSection();

    fireEvent.click(screen.getByRole('button', { name: 'Not the same person' }));
    await waitFor(() =>
      expect(callersAPI.dismiss).toHaveBeenCalledWith(['2125555555', '2128888888'])
    );
    await waitFor(() => expect(callersAPI.getSuggestions).toHaveBeenCalledTimes(2));

    fireEvent.click(screen.getByRole('button', { name: 'Name too common' }));
    await waitFor(() => expect(callersAPI.markCommon).toHaveBeenCalledWith('John Doe'));
    await waitFor(() => expect(callersAPI.getSuggestions).toHaveBeenCalledTimes(3));
  });

  it('shows one name from analytics, resolved or not, with its callers', async () => {
    vi.mocked(callersAPI.getSuggestions).mockResolvedValue([
      suggestion({
        status: 'linked',
        status_label: 'Linked',
        phones: [phone('2125555555', { caller_id: 4 }), phone('2128888888', { caller_id: 4 })],
      }),
    ]);
    vi.mocked(callersAPI.list).mockResolvedValue([caller(), caller({ id: 9, note: 'Other' })]);
    await renderSection('/admin?caller=John%20Doe#linked-callers');

    expect(callersAPI.getSuggestions).toHaveBeenCalledWith(false, 'John Doe');
    expect(screen.getByText(/Showing “John Doe”/)).toBeInTheDocument();
    expect(screen.getByText('Same voice')).toBeInTheDocument();
    expect(screen.queryByText('Other')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Link checked numbers' })).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: 'Show everyone' }));
    await waitFor(() =>
      expect(callersAPI.getSuggestions).toHaveBeenLastCalledWith(false, undefined)
    );
    expect(await screen.findByText('Other')).toBeInTheDocument();
  });

  it('flags a linked number with no wins and removes it', async () => {
    vi.mocked(callersAPI.getSuggestions).mockResolvedValue([]);
    vi.mocked(callersAPI.list).mockResolvedValue([caller()]);
    vi.mocked(callersAPI.unlinkPhone).mockResolvedValue(null);
    await renderSection();

    expect(
      screen.getByText(/\(212\) 888-8888 is linked but has no wins any more/)
    ).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button', { name: 'Remove' })[1]);
    await waitFor(() => expect(callersAPI.unlinkPhone).toHaveBeenCalledWith(4, '2128888888'));
    await waitFor(() => expect(callersAPI.list).toHaveBeenCalledTimes(2));
  });

  it('links numbers found by searching', async () => {
    vi.mocked(callersAPI.getSuggestions).mockResolvedValue([]);
    vi.mocked(callersAPI.search).mockResolvedValue([
      phone('5105550001', { names: ['Bob Smith'] }),
      phone('5105550002', { names: ['Robert Smith'] }),
    ]);
    vi.mocked(callersAPI.preview).mockResolvedValue({
      phones: ['5105550001', '5105550002'],
      caller_ids: [],
      already_linked: false,
    });
    await renderSection();

    fireEvent.change(screen.getByLabelText('Name or phone number'), { target: { value: 'smith' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    await screen.findByText(/Robert Smith/);
    expect(callersAPI.search).toHaveBeenCalledWith('smith');

    fireEvent.click(screen.getByLabelText(/Bob Smith/));
    fireEvent.click(screen.getByLabelText(/Robert Smith/));
    fireEvent.click(screen.getByRole('button', { name: 'Link checked numbers' }));
    expect(await screen.findByRole('dialog', { name: 'Confirm linking' })).toBeInTheDocument();
  });

  it('shows a load error', async () => {
    vi.mocked(callersAPI.getSuggestions).mockRejectedValue({ detail: 'Nope' });
    await renderSection();

    expect(screen.getByText('Nope')).toBeInTheDocument();
  });
});
