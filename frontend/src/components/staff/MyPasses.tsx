import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { passesAPI } from '../../services/api';
import type { PassResponse, APIError } from '../../types';
import { formatPhone } from '../../utils';
import { useAuth } from '../../contexts/authHooks';

const MyPasses = () => {
  const { user } = useAuth();
  const [passes, setPasses] = useState<PassResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const profile = user?.profile;
  const isSublistDj = profile && 'is_sublist_dj' in profile && profile.is_sublist_dj;
  const djName = profile && 'dj_name' in profile ? profile.dj_name : null;

  const loadPasses = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await passesAPI.getStaffMyGiveaways();
      setPasses(data);
      setLoaded(true);
    } catch (err) {
      const apiError = err as APIError;
      setError(
        typeof apiError.detail === 'string'
          ? apiError.detail
          : 'Failed to load giveaway history'
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isSublistDj) {
      loadPasses();
    }
  }, [isSublistDj, loadPasses]);

  const formatStatus = (status: string) => {
    const map: Record<string, string> = {
      given_away: 'Given Away',
      available: 'Available',
      claimed: 'Claimed',
    };
    return map[status] ?? status;
  };

  const formatDateTime = (dateTimeStr: string) => {
    const date = new Date(dateTimeStr);
    return date.toLocaleString('en-US', {
      weekday: 'short',
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  };

  const formatDate = (dateStr: string) => {
    const [y, m, d] = dateStr.split('-').map(Number);
    const date = new Date(y, m - 1, d);
    return date.toLocaleDateString('en-US', {
      weekday: 'short',
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  if (!isSublistDj) {
    return (
      <div className="my-passes">
        <div className="page-header">
          <h2>My Giveaway History</h2>
        </div>
        <div className="error">
          <p>This page is only available to Sublist DJ staff members.</p>
        </div>
      </div>
    );
  }

  const givenAwayPasses = passes.filter((p) => p.status === 'given_away');
  const preassignedPasses = passes.filter((p) => p.status === 'available' && p.preassigned_dj);

  return (
    <div className="my-passes">
      <div className="page-header">
        <h2>My Giveaway History</h2>
        {djName && <p className="dj-name-display">DJ Name: <strong>{djName}</strong></p>}
      </div>

      {loading && <p>Loading...</p>}

      {error && (
        <div className="error">
          <p>Error: {error}</p>
        </div>
      )}

      {loaded && !loading && passes.length === 0 && (
        <div className="no-passes">
          <p>No giveaways found{djName ? <> for <strong>{djName}</strong></> : null}.</p>
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
                  <Link to={`/staff/shows/${pass.show_id}`} className="btn-primary">
                    View Show
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
                      <span className="info-label">Winner:</span>
                      <span className="info-value">{pass.recipient_name}</span>
                    </div>
                    <div className="info-row">
                      <span className="info-label">Phone:</span>
                      <span className="info-value">{formatPhone(pass.recipient_phone)}</span>
                    </div>
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
