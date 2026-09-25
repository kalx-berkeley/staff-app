import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { passesAPI, lotteryAPI, alternatesAPI } from '../../services/api';
import type { PassResponse, MyLotteryEntryResponse, MyAlternateEntry, APIError } from '../../types';
import { formatPhone } from '../../utils';
import { useAuth } from '../../contexts/authHooks';
import { usePageTitle } from '../../hooks/usePageTitle';

const formatDateTime = (dateTimeStr: string) => {
  const date = new Date(dateTimeStr);
  return date.toLocaleString('en-US', {
    timeZone: 'America/Los_Angeles',
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

const MyPasses = () => {
  usePageTitle('My Passes · Staff');
  const { user } = useAuth();

  const profile = user?.profile;
  const isSublistDj = !!(profile && 'is_sublist_dj' in profile && profile.is_sublist_dj);
  const djName = profile && 'dj_name' in profile ? profile.dj_name : null;

  // Claimed staff passes — available to any staff/promotions member.
  const [claimedPasses, setClaimedPasses] = useState<PassResponse[]>([]);
  const [claimedLoading, setClaimedLoading] = useState(false);
  const [claimedLoaded, setClaimedLoaded] = useState(false);
  const [claimedError, setClaimedError] = useState<string | null>(null);

  // Lottery entries — available to any staff/promotions member; includes
  // DJ pass-pair entries for Sublist DJs.
  const [lotteryEntries, setLotteryEntries] = useState<MyLotteryEntryResponse[]>([]);
  const [lotteryLoading, setLotteryLoading] = useState(false);
  const [lotteryLoaded, setLotteryLoaded] = useState(false);
  const [lotteryError, setLotteryError] = useState<string | null>(null);

  // Giveaway history — Sublist DJs only.
  const [passes, setPasses] = useState<PassResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadClaimedPasses = useCallback(async () => {
    try {
      setClaimedLoading(true);
      setClaimedError(null);
      const data = await passesAPI.getStaffMyClaims();
      setClaimedPasses(data);
      setClaimedLoaded(true);
    } catch (err) {
      const apiError = err as APIError;
      setClaimedError(
        typeof apiError.detail === 'string'
          ? apiError.detail
          : 'Failed to load claimed passes'
      );
    } finally {
      setClaimedLoading(false);
    }
  }, []);

  const loadLotteryEntries = useCallback(async () => {
    try {
      setLotteryLoading(true);
      setLotteryError(null);
      const data = await lotteryAPI.getMyEntries();
      setLotteryEntries(data);
      setLotteryLoaded(true);
    } catch (err) {
      const apiError = err as APIError;
      setLotteryError(
        typeof apiError.detail === 'string'
          ? apiError.detail
          : 'Failed to load lottery entries'
      );
    } finally {
      setLotteryLoading(false);
    }
  }, []);

  // Alternate-list entries — only shown when the user is waiting somewhere.
  const [alternateEntries, setAlternateEntries] = useState<MyAlternateEntry[]>([]);
  const [alternateError, setAlternateError] = useState<string | null>(null);
  const [leavingShowId, setLeavingShowId] = useState<number | null>(null);

  const loadAlternateEntries = useCallback(async () => {
    try {
      setAlternateError(null);
      setAlternateEntries(await alternatesAPI.getMyEntries());
    } catch (err) {
      const apiError = err as APIError;
      setAlternateError(
        typeof apiError.detail === 'string'
          ? apiError.detail
          : 'Failed to load alternate list entries'
      );
    }
  }, []);

  const handleLeaveAlternates = async (showId: number) => {
    setLeavingShowId(showId);
    try {
      await alternatesAPI.leave(showId);
      await loadAlternateEntries();
    } catch (err) {
      const apiError = err as APIError;
      setAlternateError(
        typeof apiError.detail === 'string' ? apiError.detail : 'Failed to leave the alternate list'
      );
    } finally {
      setLeavingShowId(null);
    }
  };

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
    loadClaimedPasses();
    loadLotteryEntries();
    loadAlternateEntries();
  }, [loadClaimedPasses, loadLotteryEntries, loadAlternateEntries]);

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

  const givenAwayPasses = passes.filter((p) => p.status === 'given_away');
  const preassignedPasses = passes.filter((p) => p.status === 'available' && p.preassigned_dj);

  return (
    <div className="my-passes">
      <div className="page-header">
        <h2>My Passes</h2>
      </div>

      <div className="passes-list-section">
        <h3 className="passes-section-title">Claimed Staff Passes</h3>

        {claimedLoading && <p>Loading...</p>}

        {claimedError && (
          <div className="error">
            <p>Error: {claimedError}</p>
          </div>
        )}

        {claimedLoaded && !claimedLoading && claimedPasses.length === 0 && (
          <div className="no-passes">
            <p>You haven't claimed any staff passes.</p>
          </div>
        )}

        {claimedPasses.length > 0 && (
          <div className="passes-list">
            {claimedPasses.map((pass) => (
              <div key={pass.id} className="pass-card">
                <div className="pass-header">
                  <h3>{pass.show_event_name || 'Show'}</h3>
                  <span className="pass-status">{formatStatus(pass.status)}</span>
                </div>

                <div className="pass-body">
                  <div className="pass-info">
                    {pass.show_venue_name && (
                      <div className="info-row">
                        <span className="info-label">Venue:</span>
                        <span className="info-value">{pass.show_venue_name}</span>
                      </div>
                    )}
                    {pass.show_date && (
                      <div className="info-row">
                        <span className="info-label">Date:</span>
                        <span className="info-value">{formatDate(pass.show_date)}</span>
                      </div>
                    )}
                    {pass.has_guest && (
                      <div className="info-row">
                        <span className="info-label">+1 Guest:</span>
                        <span className="info-value">{pass.guest_name || 'Reserved'}</span>
                      </div>
                    )}
                    {pass.claimed_at && (
                      <div className="info-row">
                        <span className="info-label">Claimed:</span>
                        <span className="info-value">{formatDateTime(pass.claimed_at)}</span>
                      </div>
                    )}
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
        )}
      </div>

      <div className="passes-list-section">
        <h3 className="passes-section-title">My Lottery Entries</h3>

        {lotteryLoading && <p>Loading...</p>}

        {lotteryError && (
          <div className="error">
            <p>Error: {lotteryError}</p>
          </div>
        )}

        {lotteryLoaded && !lotteryLoading && lotteryEntries.length === 0 && (
          <div className="no-passes">
            <p>You aren't currently entered in any lotteries.</p>
          </div>
        )}

        {lotteryEntries.length > 0 && (
          <div className="passes-list">
            {lotteryEntries.map((entry) => (
              <div key={entry.id} className="pass-card">
                <div className="pass-header">
                  <h3>{entry.show_event_name || 'Show'}</h3>
                  <span className="pass-status">Pending</span>
                </div>

                <div className="pass-body">
                  <div className="pass-info">
                    <div className="info-row">
                      <span className="info-label">Entry Type:</span>
                      <span className="info-value">
                        {entry.entry_type === 'dj' ? 'Pass Pair (DJ)' : 'Staff Pass'}
                      </span>
                    </div>
                    {entry.show_venue_name && (
                      <div className="info-row">
                        <span className="info-label">Venue:</span>
                        <span className="info-value">{entry.show_venue_name}</span>
                      </div>
                    )}
                    {entry.show_date && (
                      <div className="info-row">
                        <span className="info-label">Show Date:</span>
                        <span className="info-value">{formatDate(entry.show_date)}</span>
                      </div>
                    )}
                    {entry.entry_type === 'dj' && entry.specialty_show_name && (
                      <div className="info-row">
                        <span className="info-label">Specialty Show:</span>
                        <span className="info-value">{entry.specialty_show_name}</span>
                      </div>
                    )}
                    {entry.entry_type === 'dj' && entry.assignment_date && (
                      <div className="info-row">
                        <span className="info-label">Requested Date:</span>
                        <span className="info-value">{formatDate(entry.assignment_date)}</span>
                      </div>
                    )}
                    {entry.entry_type === 'staff' && entry.has_guest && (
                      <div className="info-row">
                        <span className="info-label">+1 Guest:</span>
                        <span className="info-value">{entry.guest_name || 'Requested'}</span>
                      </div>
                    )}
                    <div className="info-row">
                      <span className="info-label">Entered:</span>
                      <span className="info-value">{formatDateTime(entry.entered_at)}</span>
                    </div>
                  </div>
                </div>

                <div className="show-card-footer">
                  <Link to={`/staff/shows/${entry.show_id}`} className="btn-primary">
                    View Show
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {(alternateEntries.length > 0 || alternateError) && (
        <div className="passes-list-section">
          <h3 className="passes-section-title">Alternate Lists</h3>

          {alternateError && (
            <div className="error">
              <p>Error: {alternateError}</p>
            </div>
          )}

          <div className="passes-list">
            {alternateEntries.map((entry) => (
              <div key={entry.id} className="pass-card alternate-card">
                <div className="pass-header">
                  <h3>{entry.show_event_name || 'Show'}</h3>
                  <span className="pass-status alternate-label">Alternate #{entry.position}</span>
                </div>

                <div className="pass-body">
                  <div className="pass-info">
                    {entry.show_venue_name && (
                      <div className="info-row">
                        <span className="info-label">Venue:</span>
                        <span className="info-value">{entry.show_venue_name}</span>
                      </div>
                    )}
                    {entry.show_date && (
                      <div className="info-row">
                        <span className="info-label">Show Date:</span>
                        <span className="info-value">{formatDate(entry.show_date)}</span>
                      </div>
                    )}
                    <div className="info-row">
                      <span className="info-label">Ahead of you:</span>
                      <span className="info-value">
                        {entry.position === 1 ? 'Nobody — you are next' : entry.position - 1}
                      </span>
                    </div>
                    {entry.has_guest && (
                      <div className="info-row">
                        <span className="info-label">+1 Guest:</span>
                        <span className="info-value">
                          {entry.guest_name || 'Requested'}
                          {entry.only_attend_with_guest ? ' (only attending with guest)' : ''}
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="show-card-footer">
                  <Link to={`/staff/shows/${entry.show_id}`} className="btn-primary">
                    View Show
                  </Link>
                  <button
                    onClick={() => handleLeaveAlternates(entry.show_id)}
                    className="btn-small btn-danger"
                    disabled={leavingShowId === entry.show_id}
                  >
                    {leavingShowId === entry.show_id ? 'Leaving…' : 'Leave list'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {isSublistDj && (
        <div className="passes-list-section">
          <h3 className="passes-section-title">My Giveaway History</h3>
          {djName && <p className="dj-name-display">DJ Name: <strong>{djName}</strong></p>}

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
      )}
    </div>
  );
};

export default MyPasses;
