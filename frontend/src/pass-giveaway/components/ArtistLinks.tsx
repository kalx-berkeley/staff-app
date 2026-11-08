import type { ReactNode } from 'react';
import type { ArtistLink, ArtistLinkType } from '../types';
import { linkLabel } from './artistLinkLabels';

const strokeProps = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
};

const ICONS: Record<ArtistLinkType, ReactNode> = {
  'official homepage': (
    <g {...strokeProps}>
      <path d="M3 11.5 12 4l9 7.5" />
      <path d="M5.5 9.5V20h4.5v-6h4v6h4.5V9.5" />
    </g>
  ),
  bandcamp: <path d="M1 18.5 7.6 5.5H23l-6.6 13z" fill="currentColor" />,
  discogs: (
    <g>
      <circle cx="12" cy="12" r="10" {...strokeProps} />
      <circle cx="12" cy="12" r="6" {...strokeProps} strokeWidth={1.25} />
      <circle cx="12" cy="12" r="2" fill="currentColor" />
    </g>
  ),
  lyrics: (
    <g {...strokeProps}>
      <path d="M4 4h16v12H10l-5 4v-4H4z" />
      <path d="M8 8.5h8M8 12h5" />
    </g>
  ),
  'free streaming': (
    <g>
      <circle cx="12" cy="12" r="10" {...strokeProps} />
      <path d="M10 8v8l6-4z" fill="currentColor" />
    </g>
  ),
  soundcloud: (
    <g>
      <path d="M2 13.5v3.5M4.75 11v6M7.5 9.5V17" {...strokeProps} />
      <path
        d="M10 17V8.4a5.5 5.5 0 0 1 9.4 3.1A2.8 2.8 0 0 1 20.2 17z"
        fill="currentColor"
      />
    </g>
  ),
};

interface ArtistLinksProps {
  links: ArtistLink[];
}

/** A row of icons linking to an artist's homepage, Bandcamp, Discogs and so on. */
export default function ArtistLinks({ links }: ArtistLinksProps) {
  if (links.length === 0) return null;
  return (
    <div className="band-popup__links">
      {links.map((link) => {
        const label = linkLabel(link);
        return (
          <a
            key={`${link.type} ${link.url}`}
            href={link.url}
            target="_blank"
            rel="noopener noreferrer"
            className="band-popup__link-icon"
            title={label}
            aria-label={label}
          >
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
              {ICONS[link.type]}
            </svg>
          </a>
        );
      })}
    </div>
  );
}
