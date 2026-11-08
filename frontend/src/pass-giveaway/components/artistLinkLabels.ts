import type { ArtistLink } from '../types';

/** Friendly names for common lyrics and free streaming sites. */
const SITE_NAMES: Record<string, string> = {
  'open.spotify.com': 'Spotify',
  'spotify.com': 'Spotify',
  'youtube.com': 'YouTube',
  'music.youtube.com': 'YouTube Music',
  'deezer.com': 'Deezer',
  'audiomack.com': 'Audiomack',
  'archive.org': 'the Internet Archive',
  'genius.com': 'Genius',
  'musixmatch.com': 'Musixmatch',
  'lyrics.com': 'Lyrics.com',
};

/** The site a URL is on: a friendly name if known, otherwise its host name. */
export function siteName(url: string): string {
  let host: string;
  try {
    host = new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
  return SITE_NAMES[host] ?? host;
}

/** The tooltip (and accessible name) for a link. */
export function linkLabel(link: ArtistLink): string {
  switch (link.type) {
    case 'official homepage':
      return `Official homepage (${siteName(link.url)})`;
    case 'bandcamp':
      return 'Bandcamp';
    case 'discogs':
      return 'Discogs';
    case 'lyrics':
      return `Lyrics on ${siteName(link.url)}`;
    case 'free streaming':
      return `Stream for free on ${siteName(link.url)}`;
    case 'soundcloud':
      return 'SoundCloud';
  }
}
