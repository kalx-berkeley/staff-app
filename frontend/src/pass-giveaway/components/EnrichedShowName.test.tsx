import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent, within } from '@testing-library/react';
import EnrichedShowName from './EnrichedShowName';
import { showsAPI } from '../api';
import { renderAndSettle } from '../../test/render';
import type { ShowBand } from '../types';

vi.mock('../api', () => ({
  showsAPI: {
    getArtistInfo: vi.fn(),
  },
}));

const band: ShowBand = {
  id: 1,
  show_id: 1,
  musicbrainz_id: 'abc',
  band_name: 'Wolf Parade',
  start_pos: 0,
  end_pos: 11,
  artist_type: 'Group',
  artist_country: 'CA',
  artist_disambiguation: null,
  artist_tags: null,
};

describe('EnrichedShowName band popup', () => {
  beforeEach(() => {
    vi.mocked(showsAPI.getArtistInfo).mockReset();
    globalThis.ResizeObserver ??= class {
      observe() {}
      disconnect() {}
      unobserve() {}
    } as unknown as typeof ResizeObserver;
  });

  it("shows icon links to the artist's pages, with tooltips", async () => {
    vi.mocked(showsAPI.getArtistInfo).mockResolvedValue({
      extract: null,
      wikipedia_url: null,
      links: [
        { type: 'official homepage', url: 'https://www.wolfparade.com/' },
        { type: 'bandcamp', url: 'https://wolfparade.bandcamp.com' },
        { type: 'discogs', url: 'https://www.discogs.com/artist/1' },
        { type: 'lyrics', url: 'https://genius.com/artists/Wolf-parade' },
        { type: 'free streaming', url: 'https://open.spotify.com/artist/x' },
        { type: 'soundcloud', url: 'https://soundcloud.com/wolfparade' },
      ],
    });

    await renderAndSettle(<EnrichedShowName eventName="Wolf Parade" bands={[band]} />);
    fireEvent.click(screen.getByRole('button', { name: 'Wolf Parade' }));

    const homepage = await screen.findByRole('link', {
      name: 'Official homepage (wolfparade.com)',
    });
    expect(homepage).toHaveAttribute('href', 'https://www.wolfparade.com/');
    expect(homepage).toHaveAttribute('title', 'Official homepage (wolfparade.com)');
    expect(homepage).toHaveAttribute('target', '_blank');

    const labels = [
      'Bandcamp',
      'Discogs',
      'Lyrics on Genius',
      'Stream for free on Spotify',
      'SoundCloud',
    ];
    for (const label of labels) {
      expect(screen.getByRole('link', { name: label })).toHaveAttribute('title', label);
    }
    expect(showsAPI.getArtistInfo).toHaveBeenCalledWith('abc');
  });

  it('shows no icons when the artist has no links', async () => {
    vi.mocked(showsAPI.getArtistInfo).mockResolvedValue({
      extract: null,
      wikipedia_url: null,
      links: [],
    });

    const { container } = await renderAndSettle(
      <EnrichedShowName eventName="Wolf Parade" bands={[band]} />
    );
    fireEvent.click(screen.getByRole('button', { name: 'Wolf Parade' }));

    const mbLink = await screen.findByRole('link', { name: /view on musicbrainz/i });
    const popup = mbLink.closest('.band-popup') as HTMLElement;
    expect(within(popup).getAllByRole('link')).toHaveLength(1);
    expect(container.querySelector('.band-popup__links')).toBeNull();
  });

  it("doesn't make a band with no MusicBrainz match clickable", async () => {
    const unmatched: ShowBand = {
      ...band,
      musicbrainz_id: null,
      artist_type: null,
      artist_country: null,
    };

    await renderAndSettle(<EnrichedShowName eventName="Wolf Parade" bands={[unmatched]} />);

    expect(screen.queryByRole('button', { name: 'Wolf Parade' })).toBeNull();
    const tag = screen.getByText('Wolf Parade');
    expect(tag).toHaveClass('band-tag-unmatched');
    expect(tag).toHaveAttribute('title', 'Wolf Parade (no MusicBrainz match)');
    fireEvent.click(tag);
    expect(document.querySelector('.band-popup')).toBeNull();
    expect(showsAPI.getArtistInfo).not.toHaveBeenCalled();
  });
});
