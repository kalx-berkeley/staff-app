import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { renderAndSettle } from '../test/render';
import { adminAPI } from './api';
import ShortLinksSection from './ShortLinksSection';
import type { ShortLink } from './types';

vi.mock('./api', () => ({
  adminAPI: {
    listShortLinks: vi.fn(),
    createShortLink: vi.fn(),
    updateShortLink: vi.fn(),
    deleteShortLink: vi.fn(),
  },
}));

const link = (overrides: Partial<ShortLink> = {}): ShortLink => ({
  id: 1,
  slug: 'fundraiser',
  target_url: 'https://example.com/give',
  note: 'Fall drive',
  created_by_email: 'head@example.com',
  created_at: '2026-10-17T12:00:00Z',
  updated_at: '2026-10-17T12:00:00Z',
  ...overrides,
});

const rowFor = (slug: string) => screen.getByText(`/go/${slug}`).closest('tr')!;

describe('ShortLinksSection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(adminAPI.listShortLinks).mockResolvedValue([
      link(),
      link({ id: 2, slug: 'schedule', target_url: 'https://example.org/sched', note: null }),
    ]);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('lists the links and filters them', async () => {
    await renderAndSettle(<ShortLinksSection />);

    const row = rowFor('fundraiser');
    expect(within(row).getByRole('link', { name: 'https://example.com/give' })).toHaveAttribute(
      'href',
      'https://example.com/give'
    );
    expect(within(row).getByText('Fall drive')).toBeInTheDocument();
    expect(within(row).getByText('head@example.com')).toBeInTheDocument();

    fireEvent.change(screen.getByRole('searchbox', { name: 'Filter short links' }), {
      target: { value: 'SCHED' },
    });

    expect(screen.queryByText('/go/fundraiser')).not.toBeInTheDocument();
    expect(screen.getByText('/go/schedule')).toBeInTheDocument();
  });

  it('creates a link and adds it in slug order', async () => {
    vi.mocked(adminAPI.createShortLink).mockResolvedValue(
      link({ id: 3, slug: 'party', target_url: 'https://example.net/', note: null })
    );
    await renderAndSettle(<ShortLinksSection />);

    fireEvent.change(screen.getByRole('textbox', { name: 'Slug' }), {
      target: { value: 'Party' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: 'Target URL' }), {
      target: { value: 'https://example.net/' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    expect(await screen.findByText('/go/party')).toBeInTheDocument();
    expect(adminAPI.createShortLink).toHaveBeenCalledWith({
      slug: 'Party',
      target_url: 'https://example.net/',
      note: null,
    });
    const slugs = within(screen.getByRole('table'))
      .getAllByText(/^\/go\//)
      .map((el) => el.textContent);
    expect(slugs).toEqual(['/go/fundraiser', '/go/party', '/go/schedule']);
    expect(screen.getByRole('textbox', { name: 'Slug' })).toHaveValue('');
  });

  it('shows why a link could not be created', async () => {
    vi.mocked(adminAPI.createShortLink).mockRejectedValue({
      detail: "There's already a short link /go/fundraiser.",
    });
    await renderAndSettle(<ShortLinksSection />);

    fireEvent.change(screen.getByRole('textbox', { name: 'Slug' }), {
      target: { value: 'FUNDRAISER' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: 'Target URL' }), {
      target: { value: 'https://example.net/' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    expect(
      await screen.findByText("There's already a short link /go/fundraiser.")
    ).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Slug' })).toHaveValue('FUNDRAISER');
  });

  it('edits a link in place', async () => {
    vi.mocked(adminAPI.updateShortLink).mockResolvedValue(
      link({ slug: 'drive', target_url: 'https://example.com/new', note: null })
    );
    await renderAndSettle(<ShortLinksSection />);

    fireEvent.click(screen.getByRole('button', { name: 'Edit /go/fundraiser' }));
    fireEvent.change(screen.getByRole('textbox', { name: 'Edit slug' }), {
      target: { value: 'drive' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: 'Edit target URL' }), {
      target: { value: 'https://example.com/new' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: 'Edit note' }), {
      target: { value: '' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText('/go/drive')).toBeInTheDocument();
    expect(adminAPI.updateShortLink).toHaveBeenCalledWith(1, {
      slug: 'drive',
      target_url: 'https://example.com/new',
      note: null,
    });
    expect(screen.queryByRole('textbox', { name: 'Edit slug' })).not.toBeInTheDocument();
  });

  it('deletes a link after confirming', async () => {
    vi.mocked(adminAPI.deleteShortLink).mockResolvedValue();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    await renderAndSettle(<ShortLinksSection />);

    fireEvent.click(screen.getByRole('button', { name: 'Delete /go/fundraiser' }));

    await waitFor(() => expect(screen.queryByText('/go/fundraiser')).not.toBeInTheDocument());
    expect(confirm).toHaveBeenCalled();
    expect(adminAPI.deleteShortLink).toHaveBeenCalledWith(1);
  });

  it("doesn't delete when the confirm is cancelled", async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    await renderAndSettle(<ShortLinksSection />);

    fireEvent.click(screen.getByRole('button', { name: 'Delete /go/fundraiser' }));

    expect(adminAPI.deleteShortLink).not.toHaveBeenCalled();
    expect(screen.getByText('/go/fundraiser')).toBeInTheDocument();
  });

  it('copies the full short link', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    await renderAndSettle(<ShortLinksSection />);

    fireEvent.click(screen.getByRole('button', { name: 'Copy /go/schedule' }));

    expect(await within(rowFor('schedule')).findByText('Copied')).toBeInTheDocument();
    expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/go/schedule`);
  });
});
