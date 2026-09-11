import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { onAirAPI } from '../../services/api';
import type { SpinMatch } from '../../types';

// How often to ask the backend for new spin matches. The backend itself
// throttles its own Spinitron calls independently (see spin_match_service.py),
// so this only controls how quickly a DJ finds out about a match already
// sitting in the backend's cache.
const POLL_INTERVAL_MS = 30000;

const formatShowDate = (dateStr: string) => {
  const [y, m, d] = dateStr.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  });
};

/**
 * Polls for recently played spins that match a show with passes to give
 * away, and pops up a dismissible toast for each one pointing the DJ at
 * `/dj/shows/:id`. Mounted once in DJLayout so it's active across every DJ
 * page. The backend guarantees each spin is only ever returned once (see
 * GET /api/dj/spin-matches), so toasts are additive here — no client-side
 * dedup needed, and a toast persists until the DJ dismisses it or clicks
 * through, rather than auto-expiring, since the point is to still be there
 * at the next mic break.
 */
const SpinMatchNotifier = () => {
  const [matches, setMatches] = useState<SpinMatch[]>([]);

  useEffect(() => {
    let cancelled = false;

    const poll = () => {
      onAirAPI
        .getSpinMatches()
        .then((newMatches) => {
          if (cancelled || newMatches.length === 0) return;
          setMatches((prev) => [...prev, ...newMatches]);
        })
        .catch(() => {});
    };

    poll();
    const interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  if (matches.length === 0) return null;

  const dismiss = (spinId: number) => {
    setMatches((prev) => prev.filter((m) => m.spin_id !== spinId));
  };

  return (
    <div className="spin-match-toast-container" role="status" aria-live="polite">
      {matches.map((match) => (
        <div className="spin-match-toast" key={match.spin_id}>
          <button
            className="spin-match-toast-close"
            onClick={() => dismiss(match.spin_id)}
            aria-label="Dismiss"
          >
            ×
          </button>
          {match.image && (
            <img className="spin-match-toast-image" src={match.image} alt="" />
          )}
          <div className="spin-match-toast-body">
            <p className="spin-match-toast-headline">You just played {match.artist}!</p>
            <p className="spin-match-toast-detail">
              We have passes to give away for <strong>{match.show.event_name}</strong> at{' '}
              {match.show.venue_name} on {formatShowDate(match.show.show_date)}.
            </p>
            <Link
              className="spin-match-toast-link"
              to={`/dj/shows/${match.show.id}`}
              onClick={() => dismiss(match.spin_id)}
            >
              Go to show →
            </Link>
          </div>
        </div>
      ))}
    </div>
  );
};

export default SpinMatchNotifier;
