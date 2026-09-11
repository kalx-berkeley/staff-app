import { useState, useRef, useEffect, useLayoutEffect } from 'react';
import type { FeatureBinMatch, FeatureBinDot } from '../../types';

interface FeatureBinBadgeProps {
  releases: FeatureBinMatch[];
}

const DOT_LABELS: Record<FeatureBinDot, string> = {
  RED: 'Red dot — will be added to the library',
  YLW: 'Yellow dot — donated, new to KALX but not a recent release',
  GRN: 'Green dot — will be sold, not added to the library',
  G2R: 'Green dot converted to red — will be added to the library',
};

function FeatureBinDotSwatch({ dot }: { dot: FeatureBinDot | null }) {
  if (!dot) return null;
  return (
    <span
      className={`feature-bin-dot feature-bin-dot-${dot.toLowerCase()}`}
      title={DOT_LABELS[dot] ?? dot}
    />
  );
}

interface FeatureBinPopupProps {
  releases: FeatureBinMatch[];
  onClose: () => void;
  anchorRect: DOMRect;
}

function FeatureBinPopup({ releases, onClose, anchorRect }: FeatureBinPopupProps) {
  const popupRef = useRef<HTMLDivElement>(null);

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
      className="band-popup feature-bin-popup"
      style={{ position: 'fixed', zIndex: 2000, visibility: 'hidden' }}
    >
      <div className="band-popup__header">
        <strong className="band-popup__name">In the Feature Bin</strong>
        <button className="btn-close" onClick={onClose} aria-label="Close">×</button>
      </div>
      {releases.map((release, i) => (
        <div className="feature-bin-release" key={i}>
          <div className="feature-bin-release__title">
            <FeatureBinDotSwatch dot={release.dot} />
            <strong>{release.album}</strong>
          </div>
          <div className="band-popup__meta">
            {release.artist}
            {release.added_date && ` · added ${release.added_date}`}
          </div>
          {release.media_url && (
            <a
              href={release.media_url}
              target="_blank"
              rel="noopener noreferrer"
              className="band-popup__wiki-link"
            >
              Listen ↗
            </a>
          )}
        </div>
      ))}
    </div>
  );
}

export default function FeatureBinBadge({ releases }: FeatureBinBadgeProps) {
  const [open, setOpen] = useState<DOMRect | null>(null);

  if (!releases || releases.length === 0) return null;

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    setOpen(open ? null : e.currentTarget.getBoundingClientRect());
  };

  return (
    <>
      <button
        type="button"
        className="status-badge status-feature-bin"
        onClick={handleClick}
        title="This show has an artist with a release in the feature bin — click for details"
      >
        ★ Feature Bin
      </button>
      {open && (
        <FeatureBinPopup releases={releases} anchorRect={open} onClose={() => setOpen(null)} />
      )}
    </>
  );
}
