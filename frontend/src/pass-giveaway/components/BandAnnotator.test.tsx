import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, screen, fireEvent } from '@testing-library/react';
import BandAnnotator from './BandAnnotator';
import { showsAPI } from '../api';
import { renderAndSettle } from '../../test/render';

vi.mock('../api', () => ({
  showsAPI: {
    searchMusicBrainz: vi.fn(),
  },
}));

/** Select characters [start, end) of a text node, as a long-press would. */
const selectText = (textNode: Node, start: number, end: number) => {
  const range = document.createRange();
  range.setStart(textNode, start);
  range.setEnd(textNode, end);
  const sel = window.getSelection()!;
  sel.removeAllRanges();
  sel.addRange(range);
  act(() => {
    document.dispatchEvent(new Event('selectionchange'));
  });
};

describe('BandAnnotator — selecting without a mouse', () => {
  beforeEach(() => {
    vi.mocked(showsAPI.searchMusicBrainz).mockReset();
    // jsdom doesn't lay out text, so ranges have no geometry of their own.
    Range.prototype.getBoundingClientRect = () => new DOMRect(0, 0, 10, 10);
    globalThis.ResizeObserver ??= class {
      observe() {}
      disconnect() {}
      unobserve() {}
    } as unknown as typeof ResizeObserver;
  });

  afterEach(() => {
    window.getSelection()?.removeAllRanges();
  });

  it('offers a Tag button for the selection and searches when it is tapped', async () => {
    vi.mocked(showsAPI.searchMusicBrainz).mockResolvedValue([
      { id: 'abc', name: 'Wolf Parade' },
    ]);

    await renderAndSettle(
      <BandAnnotator
        eventName="Wolf Parade with Friends"
        bands={[]}
        onEventNameChange={vi.fn()}
        onChange={vi.fn()}
      />
    );

    selectText(screen.getByRole('textbox').firstChild!, 0, 11);
    fireEvent.click(screen.getByRole('button', { name: /tag “wolf parade” as an artist/i }));

    expect(await screen.findByText('Wolf Parade', { selector: 'strong' })).toBeInTheDocument();
    expect(showsAPI.searchMusicBrainz).toHaveBeenCalledWith('Wolf Parade');
    expect(screen.queryByRole('button', { name: /as an artist/i })).not.toBeInTheDocument();
  });

  it('offers no Tag button for text that is already tagged', async () => {
    await renderAndSettle(
      <BandAnnotator
        eventName="Wolf Parade"
        bands={[
          {
            id: 1,
            show_id: 1,
            musicbrainz_id: 'abc',
            band_name: 'Wolf',
            start_pos: 0,
            end_pos: 4,
            artist_type: null,
            artist_country: null,
            artist_disambiguation: null,
            artist_tags: null,
          },
        ]}
        onEventNameChange={vi.fn()}
        onChange={vi.fn()}
      />
    );

    // "Wolf" is tagged, so the text is split into the tagged span and " Parade".
    const textbox = screen.getByRole('textbox');
    selectText(textbox.lastChild!, 1, 7);
    expect(screen.getByRole('button', { name: /tag “parade” as an artist/i })).toBeInTheDocument();

    selectText(textbox.firstChild!.firstChild!, 0, 2);
    expect(screen.queryByRole('button', { name: /as an artist/i })).not.toBeInTheDocument();
  });
});
