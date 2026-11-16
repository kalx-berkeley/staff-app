import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { passesAPI } from '../api';
import type { PassResponse } from '../types';
import { isRecentShow } from '../utils';
import type { APIError } from '../../common/types';
import { usePageTitle } from '../../common/hooks/usePageTitle';
import { formatCalendarDate, formatPacific } from '../../common/dateTime';
import { useOnAir } from './onAirContext';

/**
 * The on-air identity's giveaways and pre-assigned passes (decision 27), or
 * the next identity's after an early switch. A DJ's history across all their
 * personas and shows is on the signed-in /staff My Passes page.
 */
const MyPasses = () => {
  usePageTitle('My Passes · DJ');
  const { loaded: onAirLoaded, identity, identityKey } = useOnAir();
  const [passes, setPasses] = useState<PassResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!onAirLoaded) return;
    if (!identity) {
      setPasses([]);
      setLoaded(true);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    passesAPI
      .getMyGiveaways()
      .then((data) => {
        if (cancelled) return;
        setPasses(data);
        setLoaded(true);
      })
      .catch((err) => {
        if (cancelled) return;
        const detail = (err as APIError).detail;
        setError(typeof detail === 'string' ? detail : 'Failed to load giveaway history');
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
    // identity follows identityKey
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onAirLoaded, identityKey]);

  const formatStatus = (status: string) => {
    const map: Record<string, string> = {
      given_away: 'Given Away',
      available: 'Available',
      claimed: 'Claimed',
    };
    return map[status] ?? status;
  };

  const formatDateTime = (dateTimeStr: string) =>
    formatPacific(dateTimeStr, {
      weekday: 'short',
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });

  const formatDate = (dateStr: string) =>
    formatCalendarDate(dateStr, {
      weekday: 'short',
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });

  const recentPasses = passes.filter((p) => isRecentShow(p.show_date));
  const givenAwayPasses = recentPasses.filter((p) => p.status === 'given_away');
  const preassignedPasses = recentPasses.filter(
    (p) => p.status === 'available' && p.preassigned_dj
  );

  return (
    <div className="my-passes">
      <div className="page-header">
        <h2>My Giveaway History</h2>
      </div>

      {error && (
        <div className="error">
          <p>Error: {error}</p>
        </div>
      )}

      {loading && <div className="loading">Loading…</div>}

      {loaded && !loading && recentPasses.length === 0 && (
        <div className="no-passes">
          <p>
            {identity ? (
              <>No recent or upcoming giveaways found for <strong>{identity.name}</strong>.</>
            ) : (
              'No one is on air, so there are no passes to show.'
            )}
          </p>
        </div>
      )}

      {preassignedPasses.length > 0 && (
        <div className="passes-list-section">
          <h3 className="passes-section-title">Pre-assigned to You</h3>
          <div className="shows-grid">
            {preassignedPasses.map((pass) => (
              <div key={pass.id} className="show-card">
                <div className="show-card-header">
                  <h3>{pass.show_event_name || 'Show'}</h3>
                  <span className="pass-status pass-status-preassigned">Pre-assigned</span>
                </div>

                <div className="show-card-body">
                  <div className="show-card-details">
                    {pass.show_venue_name && (
                      <div className="info-row">
                        <span className="info-label">Venue:</span>
                        <span className="info-value">{pass.show_venue_name}</span>
                      </div>
                    )}
                    {(pass.preassigned_date || pass.show_date) && (
                      <div className="info-row">
                        <span className="info-label">Date:</span>
                        <span className="info-value">
                          {formatDate(pass.preassigned_date || pass.show_date!)}
                        </span>
                      </div>
                    )}
                    <div className="info-row">
                      <span className="info-label">Pre-assigned To:</span>
                      <span className="info-value">{pass.preassigned_dj}</span>
                    </div>
                  </div>
                </div>

                <div className="show-card-footer">
                  <Link to={`/dj/shows/${pass.show_id}`} className="btn-primary">
                    Give Away Passes
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {givenAwayPasses.length > 0 && (
        <div className="passes-list-section">
          {preassignedPasses.length > 0 && (
            <h3 className="passes-section-title">Given Away</h3>
          )}
          <div className="passes-list">
            {givenAwayPasses.map((pass) => (
              <div key={pass.id} className="pass-card">
                <div className="pass-header">
                  <h3>Pass Pair</h3>
                  <span className="pass-status">{formatStatus(pass.status)}</span>
                </div>

                <div className="pass-body">
                  <div className="pass-info">
                    {pass.show_event_name && (
                      <div className="info-row">
                        <span className="info-label">Show:</span>
                        <span className="info-value">{pass.show_event_name}</span>
                      </div>
                    )}
                    <div className="info-row">
                      <span className="info-label">Given Away By:</span>
                      <span className="info-value">{pass.given_away_by_dj}</span>
                    </div>
                    {pass.given_away_at && (
                      <div className="info-row">
                        <span className="info-label">Date/Time:</span>
                        <span className="info-value">
                          {formatDateTime(pass.given_away_at)}
                        </span>
                      </div>
                    )}
                    {pass.preassigned_dj && (
                      <div className="info-row">
                        <span className="info-label">Pre-assigned To:</span>
                        <span className="info-value">{pass.preassigned_dj}</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default MyPasses;
