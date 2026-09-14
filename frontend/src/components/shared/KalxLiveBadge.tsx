import { useState, useRef, useEffect, useLayoutEffect } from 'react';
import type { KalxLiveAppearance } from '../../types';

interface KalxLiveBadgeProps {
  appearances: KalxLiveAppearance[];
}

function formatAppearance(appearance: KalxLiveAppearance): string {
  // Parse as a local date (not UTC midnight) so the displayed day matches
  // the calendar day the band played, regardless of the viewer's timezone.
  const [year, month, day] = appearance.event_date.split('-').map(Number);
  const eventDate = new Date(year, month - 1, day);
  const formatted = eventDate.toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const verb = eventDate >= today ? 'Performing' : 'Performed';
  return `${verb} ${formatted}`;
}

interface KalxLivePopupProps {
  appearances: KalxLiveAppearance[];
  onClose: () => void;
  anchorRect: DOMRect;
}

function KalxLivePopup({ appearances, onClose, anchorRect }: KalxLivePopupProps) {
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
      className="band-popup kalx-live-popup"
      style={{ position: 'fixed', zIndex: 2000, visibility: 'hidden' }}
    >
      <div className="band-popup__header">
        <strong className="band-popup__name">On KALX Live!</strong>
        <button className="btn-close" onClick={onClose} aria-label="Close">×</button>
      </div>
      {appearances.map((appearance, i) => (
        <div className="kalx-live-appearance" key={i}>
          <strong className="kalx-live-appearance__band">{appearance.band_name}</strong>
          <div className="band-popup__meta">{formatAppearance(appearance)}</div>
        </div>
      ))}
    </div>
  );
}

export default function KalxLiveBadge({ appearances }: KalxLiveBadgeProps) {
  const [open, setOpen] = useState<DOMRect | null>(null);

  if (!appearances || appearances.length === 0) return null;

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    setOpen(open ? null : e.currentTarget.getBoundingClientRect());
  };

  return (
    <>
      <button
        type="button"
        className="status-badge status-kalx-live"
        onClick={handleClick}
        title="This show has an artist who was recently on, or will be on, KALX Live! — click for details"
      >
        🤘🏽 KALX Live!
      </button>
      {open && (
        <KalxLivePopup
          appearances={appearances}
          anchorRect={open}
          onClose={() => setOpen(null)}
        />
      )}
    </>
  );
}
