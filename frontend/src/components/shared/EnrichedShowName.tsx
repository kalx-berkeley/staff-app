import { useState, useEffect, useLayoutEffect, useRef } from 'react';
import type { ShowBand } from '../../types';
import { showsAPI } from '../../services/api';

interface EnrichedShowNameProps {
  eventName: string;
  bands: ShowBand[];
  className?: string;
  onGenreClick?: (genre: string) => void;
}

interface BandPopupProps {
  band: ShowBand;
  onClose: () => void;
  anchorRect: DOMRect;
  onGenreClick?: (genre: string) => void;
}

function BandPopup({ band, onClose, anchorRect, onGenreClick }: BandPopupProps) {
  const popupRef = useRef<HTMLDivElement>(null);
  const [extract, setExtract] = useState<string | null>(null);
  const [wikipediaUrl, setWikipediaUrl] = useState<string | null>(null);
  const [extractLoading, setExtractLoading] = useState(false);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    const handleClick = (e: MouseEvent) => {
      if (popupRef.current && !popupRef.current.contains(e.target as Node)) onClose();
    };
    document.addEventListener('keydown', handleKey);
    document.addEventListener('mousedown', handleClick);
    return () => {
      document.removeEventListener('keydown', handleKey);
      document.removeEventListener('mousedown', handleClick);
    };
  }, [onClose]);

  useEffect(() => {
    if (!band.musicbrainz_id) return;
    let cancelled = false;
    setExtractLoading(true);
    showsAPI.getArtistWikipedia(band.musicbrainz_id).then((result) => {
      if (!cancelled) {
        setExtract(result.extract);
        setWikipediaUrl(result.wikipedia_url);
        setExtractLoading(false);
      }
    });
    return () => { cancelled = true; };
  }, [band.musicbrainz_id]);

  useLayoutEffect(() => {
    const el = popupRef.current;
    if (!el) return;
    const position = () => {
      const h = el.offsetHeight;
      const left = Math.max(8, Math.min(anchorRect.left, window.innerWidth - 380));
      const top =
        window.innerHeight - anchorRect.bottom - 8 >= h
          ? anchorRect.bottom + 8
          : Math.max(8, anchorRect.top - h - 8);
      el.style.top = `${top}px`;
      el.style.left = `${left}px`;
      el.style.visibility = 'visible';
    };
    position();
    const ro = new ResizeObserver(position);
    ro.observe(el);
    return () => ro.disconnect();
  }, [anchorRect]);

  return (
    <div
      ref={popupRef}
      className="band-popup"
      style={{ position: 'fixed', zIndex: 2000, visibility: 'hidden' }}
    >
      <div className="band-popup__header">
        <strong className="band-popup__name">{band.band_name}</strong>
        <button className="btn-close" onClick={onClose} aria-label="Close">×</button>
      </div>
      {(band.artist_type || band.artist_country) && (
        <div className="band-popup__meta">
          {[band.artist_type, band.artist_country].filter(Boolean).join(' · ')}
        </div>
      )}
      {band.artist_disambiguation && (
        <div className="band-popup__disambiguation">({band.artist_disambiguation})</div>
      )}
      {band.artist_tags && band.artist_tags.length > 0 && (
        <div className="band-popup__tags">
          {band.artist_tags.map((tag) => (
            <span
              key={tag}
              className={`genre-tag${onGenreClick ? ' genre-tag-clickable' : ''}`}
              onClick={onGenreClick ? () => onGenreClick(tag) : undefined}
              role={onGenreClick ? 'button' : undefined}
              tabIndex={onGenreClick ? 0 : undefined}
              onKeyDown={onGenreClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') onGenreClick(tag); } : undefined}
              title={onGenreClick ? 'Click to filter by this genre' : undefined}
            >
              {tag}
            </span>
          ))}
        </div>
      )}
      {extractLoading && (
        <div className="band-popup__extract-loading">Loading…</div>
      )}
      {!extractLoading && extract && (
        <div className="band-popup__extract">
          {extract}
          {wikipediaUrl && (
            <a
              href={wikipediaUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="band-popup__wiki-link"
            > Read more ↗</a>
          )}
        </div>
      )}
      <a
        href={`https://musicbrainz.org/artist/${band.musicbrainz_id}`}
        target="_blank"
        rel="noopener noreferrer"
        className="band-popup__mb-link"
      >
        View on MusicBrainz ↗
      </a>
    </div>
  );
}

export default function EnrichedShowName({ eventName, bands, className, onGenreClick }: EnrichedShowNameProps) {
  const [activePopup, setActivePopup] = useState<{ band: ShowBand; rect: DOMRect } | null>(null);

  if (!bands || bands.length === 0) {
    return <span className={className}>{eventName}</span>;
  }

  const sorted = [...bands].sort((a, b) => a.start_pos - b.start_pos);
  const segments: Array<{ kind: 'text'; text: string } | { kind: 'band'; text: string; band: ShowBand }> = [];
  let cursor = 0;

  for (const band of sorted) {
    if (band.start_pos > cursor) {
      segments.push({ kind: 'text', text: eventName.slice(cursor, band.start_pos) });
    }
    segments.push({ kind: 'band', text: eventName.slice(band.start_pos, band.end_pos), band });
    cursor = band.end_pos;
  }
  if (cursor < eventName.length) {
    segments.push({ kind: 'text', text: eventName.slice(cursor) });
  }

  const handleBandClick = (band: ShowBand, e: React.MouseEvent<HTMLButtonElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    if (activePopup?.band === band) {
      setActivePopup(null);
    } else {
      setActivePopup({ band, rect });
    }
  };

  return (
    <span className={className}>
      {segments.map((seg, i) =>
        seg.kind === 'band' ? (
          <button
            key={i}
            type="button"
            className="band-link"
            onClick={(e) => handleBandClick(seg.band, e)}
            title={`${seg.band.band_name}${seg.band.artist_type ? ` (${seg.band.artist_type})` : ''}`}
          >
            {seg.text}
          </button>
        ) : (
          <span key={i}>{seg.text}</span>
        )
      )}
      {activePopup && (
        <BandPopup
          band={activePopup.band}
          anchorRect={activePopup.rect}
          onClose={() => setActivePopup(null)}
          onGenreClick={onGenreClick}
        />
      )}
    </span>
  );
}
