import { useEffect, useRef, useState } from 'react';
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

/** Identifies one notification card — a spin can match more than one show. */
const matchKey = (match: SpinMatch) => `${match.spin_id}:${match.show.id}`;

/**
 * Polls for spins currently matching a show with passes to give away, and
 * pops up a dismissible toast for each one pointing the DJ at
 * `/dj/shows/:id`. Mounted once in DJLayout so it's active across every DJ
 * page.
 *
 * GET /api/dj/spin-matches returns every current, not-yet-dismissed match
 * on every poll, so each poll result is treated as authoritative: matches
 * this tab is showing that the backend no longer returns get removed here
 * too, which is how a dismissal or "Go to show" in one tab clears the same
 * toast from every other open tab, on their next poll. dismissedKeysRef
 * guards against the reverse race — a poll already in flight when this tab
 * dismisses a toast can still land afterward with that match in it (the
 * dismiss hadn't been recorded server-side yet when that poll was sent), so
 * anything this tab has dismissed locally is filtered out of every
 * subsequent poll response regardless of what the backend says, until the
 * next poll cycle catches up. A toast otherwise persists until dismissed
 * rather than auto-expiring, since the point is to still be there at the
 * next mic break.
 */
const SpinMatchNotifier = () => {
  const [matches, setMatches] = useState<SpinMatch[]>([]);
  const dismissedKeysRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    let cancelled = false;

    const poll = () => {
      onAirAPI
        .getSpinMatches()
        .then((currentMatches) => {
          if (cancelled) return;
          const current = currentMatches.filter(
            (m) => !dismissedKeysRef.current.has(matchKey(m))
          );
          const currentKeys = new Set(current.map(matchKey));
          setMatches((prev) => {
            const stillPresent = prev.filter((m) => currentKeys.has(matchKey(m)));
            const stillPresentKeys = new Set(stillPresent.map(matchKey));
            const added = current.filter((m) => !stillPresentKeys.has(matchKey(m)));
            if (added.length === 0 && stillPresent.length === prev.length) return prev;
            return [...stillPresent, ...added];
          });
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

  const dismiss = (match: SpinMatch) => {
    dismissedKeysRef.current.add(matchKey(match));
    setMatches((prev) => prev.filter((m) => matchKey(m) !== matchKey(match)));
    onAirAPI.dismissSpinMatch(match.spin_id, match.show.id).catch(() => {});
  };

  return (
    <div className="spin-match-toast-container" role="status" aria-live="polite">
      {matches.map((match) => (
        <div className="spin-match-toast" key={matchKey(match)}>
          <button
            className="spin-match-toast-close"
            onClick={() => dismiss(match)}
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
              onClick={() => dismiss(match)}
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
