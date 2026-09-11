import { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import { passesAPI, autocompleteAPI } from '../../services/api';
import { useOnAirDj } from '../shared';
import type { PassResponse, APIError } from '../../types';
import { formatPhone } from '../../utils';

const DJ_NAME_KEY = 'kalx_dj_name';

const MyPasses = () => {
  const [djName, setDjName] = useState(localStorage.getItem(DJ_NAME_KEY) || '');
  const [passes, setPasses] = useState<PassResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Autocomplete state
  const [djNames, setDjNames] = useState<string[]>([]);
  const [filteredDjNames, setFilteredDjNames] = useState<string[]>([]);
  const [showAutocomplete, setShowAutocomplete] = useState(false);
  const autocompleteRef = useRef<HTMLUListElement>(null);

  useEffect(() => {
    autocompleteAPI.getDJNames().then(setDjNames).catch(() => {});
  }, []);

  const loadPasses = useCallback(async (name: string) => {
    if (!name.trim()) {
      setError('Please enter your DJ name');
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const data = await passesAPI.getMyGiveaways(name.trim());
      setPasses(data);
      setLoaded(true);
      localStorage.setItem(DJ_NAME_KEY, name.trim());
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
    const savedName = localStorage.getItem(DJ_NAME_KEY);
    if (savedName?.trim()) {
      loadPasses(savedName);
    }
  }, [loadPasses]);

  const handleDjNameChange = (value: string) => {
    setDjName(value);
    if (value.trim()) {
      const filtered = djNames.filter((name) =>
        name.toLowerCase().includes(value.toLowerCase())
      );
      setFilteredDjNames(filtered);
      setShowAutocomplete(filtered.length > 0);
    } else {
      setShowAutocomplete(false);
    }
  };

  const selectDjName = (name: string) => {
    setDjName(name);
    setShowAutocomplete(false);
    if (name.trim()) {
      loadPasses(name);
    } else {
      // Cleared automatically (e.g. the on-air schedule moved to a show with
      // no specific DJ) rather than searched for — don't show a "please
      // enter your DJ name" error for this.
      localStorage.setItem(DJ_NAME_KEY, '');
      setPasses([]);
      setError(null);
      setLoaded(false);
    }
  };

  const { currentDjName, mismatch, transitionNotice, dismissTransitionNotice } = useOnAirDj(
    djName,
    selectDjName
  );

  const handleDjKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      setShowAutocomplete(false);
      loadPasses(djName);
    } else if (e.key === 'Tab' && filteredDjNames.length === 1) {
      e.preventDefault();
      selectDjName(filteredDjNames[0]);
    }
  };

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

  const givenAwayPasses = passes.filter((p) => p.status === 'given_away');
  const preassignedPasses = passes.filter((p) => p.status === 'available' && p.preassigned_dj);

  return (
    <div className="my-passes">
      <div className="page-header">
        <h2>My Giveaway History</h2>
      </div>

      <div className="dj-name-filter">
        <div className="form-group-inline">
          <label htmlFor="dj-name-input">DJ Name:</label>
          <div className="autocomplete-wrapper" style={{ flex: 1, minWidth: 150 }}>
            <input
              id="dj-name-input"
              type="text"
              value={djName}
              onChange={(e) => handleDjNameChange(e.target.value)}
              onKeyDown={handleDjKeyDown}
              onBlur={() => setTimeout(() => setShowAutocomplete(false), 200)}
              placeholder="Enter your DJ name"
              autoComplete="off"
            />
            {showAutocomplete && (
              <ul className="autocomplete-list" ref={autocompleteRef}>
                {filteredDjNames.map((name) => (
                  <li
                    key={name}
                    onMouseDown={() => selectDjName(name)}
                    className="autocomplete-item"
                  >
                    {name}
                  </li>
                ))}
                {filteredDjNames.length === 1 && (
                  <li className="autocomplete-hint">Press Tab to complete</li>
                )}
              </ul>
            )}
          </div>
          <button
            onClick={() => loadPasses(djName)}
            className="btn-primary"
            disabled={loading}
          >
            {loading ? 'Loading...' : 'Load'}
          </button>
        </div>
        {mismatch && currentDjName && (
          <div className="dj-name-mismatch-warning">
            This doesn't match the scheduled on-air DJ ({currentDjName}).{' '}
            <button
              type="button"
              className="btn-secondary"
              onClick={() => selectDjName(currentDjName)}
            >
              Use {currentDjName}
            </button>
          </div>
        )}
        {transitionNotice && (
          <div className="dj-name-transition-notice">
            {transitionNotice}
            <button
              type="button"
              className="dj-name-notice-dismiss"
              aria-label="Dismiss"
              onClick={dismissTransitionNotice}
            >
              ×
            </button>
          </div>
        )}
      </div>

      {error && (
        <div className="error">
          <p>Error: {error}</p>
        </div>
      )}

      {loaded && !loading && passes.length === 0 && (
        <div className="no-passes">
          <p>No giveaways found for <strong>{djName}</strong>.</p>
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
