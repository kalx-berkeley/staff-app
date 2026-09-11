import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { showsAPI, passesAPI } from '../../services/api';
import SearchBar from '../promotions/SearchBar';
import { Tooltip, DjNameInput, DJ_NAME_KEY, EnrichedShowName, FeatureBinBadge, DatePicker } from '../shared';
import type { ShowSummary, PassResponse, APIError } from '../../types';

const VIEW_MODE_KEY = 'kalx_dj_view_mode';

const getDefaultDateFrom = (): string => {
  const d = new Date();
  d.setDate(d.getDate() - 30);
  return d.toISOString().split('T')[0];
};

const ShowBrowser = () => {
  const [rawShows, setRawShows] = useState<ShowSummary[]>([]);
  const [allShows, setAllShows] = useState<ShowSummary[]>([]);
  const [filteredShows, setFilteredShows] = useState<ShowSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedGenre, setSelectedGenre] = useState('');
  const [currentGenre, setCurrentGenre] = useState('');
  const [sortBy, setSortBy] = useState<'date' | 'band' | 'venue' | 'published'>('date');
  const [djName, setDjName] = useState(localStorage.getItem(DJ_NAME_KEY) || '');
  const [myAssignedPasses, setMyAssignedPasses] = useState<PassResponse[]>([]);
  const [showAssigned, setShowAssigned] = useState(true);
  const [viewMode, setViewMode] = useState<'card' | 'compact'>(
    (localStorage.getItem(VIEW_MODE_KEY) as 'card' | 'compact') || 'card'
  );
  const [dateFrom, setDateFrom] = useState(getDefaultDateFrom());
  const [dateTo, setDateTo] = useState('');

  const loadShows = async () => {
    try {
      setLoading(true);
      setError(null);
      const params = {
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      };
      const data = await showsAPI.list(params);
      const publishedOnly = data.filter((show) => show.status === 'published');
      setRawShows(publishedOnly);
    } catch (err) {
      const apiError = err as APIError;
      setError(
        typeof apiError.detail === 'string' ? apiError.detail : 'Failed to load shows'
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadShows();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dateFrom, dateTo]);

  useEffect(() => {
    setAllShows(rawShows);
  }, [rawShows]);

  useEffect(() => {
    if (!djName.trim()) {
      setMyAssignedPasses([]);
      return;
    }
    const timer = setTimeout(() => {
      passesAPI
        .getMyGiveaways(djName.trim())
        .then((passes) =>
          setMyAssignedPasses(
            passes.filter((p) => p.status === 'available' && !!p.preassigned_dj)
          )
        )
        .catch(() => setMyAssignedPasses([]));
    }, 300);
    return () => clearTimeout(timer);
  }, [djName]);

  const handleViewMode = (mode: 'card' | 'compact') => {
    setViewMode(mode);
    localStorage.setItem(VIEW_MODE_KEY, mode);
  };

  const assignedShowIds = new Set(myAssignedPasses.map((p) => p.show_id));

  const formatAgeRestriction = (age: string) =>
    age === 'all_ages' ? 'All Ages' : age;

  const formatDate = (dateStr: string) => {
    const [_y, _m, _d] = dateStr.split('-').map(Number); const date = new Date(_y, _m - 1, _d);
    return date.toLocaleDateString('en-US', {
      weekday: 'short',
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const formatDateShort = (dateStr: string) => {
    const [_y, _m, _d] = dateStr.split('-').map(Number); const date = new Date(_y, _m - 1, _d);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const formatTime = (timeStr: string) => {
    const [hours, minutes] = timeStr.split(':');
    const hour = parseInt(hours);
    const ampm = hour >= 12 ? 'PM' : 'AM';
    const displayHour = hour % 12 || 12;
    return `${displayHour}:${minutes} ${ampm}`;
  };

  const formatDateRange = (startDateStr: string, endDateStr: string): string => {
    const [sy, sm, sd] = startDateStr.split('-').map(Number);
    const [ey, em, ed] = endDateStr.split('-').map(Number);
    const start = new Date(sy, sm - 1, sd);
    const end = new Date(ey, em - 1, ed);
    const startFmt = start.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    const endFmt = end.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    return `${startFmt} – ${endFmt}`;
  };

  const sortedShows = [...filteredShows].sort((a, b) => {
    if (sortBy === 'date') return a.show_date.localeCompare(b.show_date);
    if (sortBy === 'band') return a.event_name.localeCompare(b.event_name);
    if (sortBy === 'published') {
      if (!a.published_at && !b.published_at) return 0;
      if (!a.published_at) return 1;
      if (!b.published_at) return -1;
      return b.published_at.localeCompare(a.published_at);
    }
    return a.venue.name.localeCompare(b.venue.name);
  });

  return (
    <div className="show-browser">
      <div className="page-header">
        <h2>Available Shows</h2>
        <p className="page-description">Browse published shows and give away passes</p>
      </div>

      <DjNameInput value={djName} onChange={setDjName} id="dj-shows-name" />

      <SearchBar shows={allShows} onSearch={setFilteredShows} externalGenre={selectedGenre} onGenreChange={setCurrentGenre} />

      <div className="sort-controls">
        <label htmlFor="dj-sort-by">Sort by:</label>
        <select
          id="dj-sort-by"
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as 'date' | 'band' | 'venue' | 'published')}
        >
          <option value="date">Date (soonest first)</option>
          <option value="band">Band name</option>
          <option value="venue">Venue name</option>
          <option value="published">Published (newest first)</option>
        </select>

        <span style={{ marginLeft: '1rem' }}>
          <label htmlFor="dj-date-from">From:</label>{' '}
          <DatePicker
            id="dj-date-from"
            value={dateFrom}
            onChange={setDateFrom}
            style={{ fontSize: '0.9rem' }}
          />
        </span>
        <span style={{ marginLeft: '0.5rem' }}>
          <label htmlFor="dj-date-to">To:</label>{' '}
          <DatePicker
            id="dj-date-to"
            value={dateTo}
            onChange={setDateTo}
            style={{ fontSize: '0.9rem' }}
          />
        </span>

        <div className="view-toggle">
          <button
            className={viewMode === 'card' ? 'active' : ''}
            onClick={() => handleViewMode('card')}
            title="Card view"
          >
            Cards
          </button>
          <button
            className={viewMode === 'compact' ? 'active' : ''}
            onClick={() => handleViewMode('compact')}
            title="Compact list view"
          >
            List
          </button>
        </div>
      </div>

      {djName.trim() && myAssignedPasses.length > 0 && (
        <div className="assigned-shows-section">
          <div className="assigned-shows-header">
            <h3>Your Pre-assigned Shows</h3>
            <button
              className="btn-secondary"
              style={{ fontSize: '0.8rem', padding: '0.2rem 0.6rem' }}
              onClick={() => setShowAssigned((v) => !v)}
            >
              {showAssigned ? 'Hide' : 'Show'}
            </button>
          </div>

          {showAssigned && (
            viewMode === 'compact' ? (
              <div className="shows-list">
                <table className="shows-list-table">
                  <thead>
                    <tr>
                      <th>Event</th>
                      <th>Venue</th>
                      <th>Date</th>
                      <th>Pre-assigned Date</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {myAssignedPasses.map((pass) => (
                      <tr key={pass.id} className="has-assignment">
                        <td>{pass.show_event_name || '—'}</td>
                        <td>{pass.show_venue_name || '—'}</td>
                        <td>{pass.show_date ? formatDateShort(pass.show_date) : '—'}</td>
                        <td>{pass.preassigned_date ? formatDateShort(pass.preassigned_date) : '—'}</td>
                        <td>
                          <Link to={`/dj/shows/${pass.show_id}`} className="btn-primary btn-sm">
                            Give Away Passes
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="shows-grid">
                {myAssignedPasses.map((pass) => (
                  <div key={pass.id} className="show-card show-card-assigned">
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
                        {(pass.show_date) && (
                          <div className="info-row">
                            <span className="info-label">Show Date:</span>
                            <span className="info-value">{formatDate(pass.show_date)}</span>
                          </div>
                        )}
                        {pass.preassigned_date && (
                          <div className="info-row">
                            <span className="info-label">For Airdate:</span>
                            <span className="info-value">{formatDate(pass.preassigned_date)}</span>
                          </div>
                        )}
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
            )
          )}
        </div>
      )}

      {error ? (
        <div className="error">
          <p>Error: {error}</p>
          <button onClick={loadShows} className="btn-primary">
            Retry
          </button>
        </div>
      ) : loading ? (
        <div className="loading">Loading shows...</div>
      ) : sortedShows.length === 0 ? (
        <div className="no-shows">
          <p>No shows available at this time.</p>
        </div>
      ) : viewMode === 'compact' ? (
        <div className="shows-list">
          <table className="shows-list-table">
            <thead>
              <tr>
                <th>Event</th>
                <th>Venue</th>
                <th>Date</th>
                <th>Time</th>
                <th>
                  Pairs
                  <Tooltip text="Available pass pairs for on-air giveaway" />
                </th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sortedShows.map((show) => {
                const noPairs = show.available_pair_count === 0;
                const hasAssignment = assignedShowIds.has(show.id);
                return (
                  <tr
                    key={show.id}
                    className={[noPairs ? 'show-dimmed' : '', hasAssignment ? 'has-assignment' : '', show.co_announce ? 'show-row-co-announce' : ''].filter(Boolean).join(' ') || undefined}
                  >
                    <td>
                      <EnrichedShowName eventName={show.event_name} bands={show.bands ?? []} onGenreClick={(g) => setSelectedGenre(currentGenre ? currentGenre + ', ' + g : g)} />
                      {hasAssignment && (
                        <span className="assignment-indicator" title="You have passes pre-assigned for this show"> ★</span>
                      )}
                      {show.co_announce && (
                        <span className="co-announce-badge" style={{ marginLeft: '0.5rem' }}>📢 Co-Announce</span>
                      )}
                      {show.in_feature_bin && (
                        <span style={{ marginLeft: '0.5rem' }}>
                          <FeatureBinBadge releases={show.feature_bin_releases} />
                        </span>
                      )}
                    </td>
                    <td>{show.venue.name}</td>
                    <td>{show.show_start_date ? formatDateRange(show.show_start_date, show.show_date) : formatDateShort(show.show_date)}</td>
                    <td>{show.show_start_date ? '—' : formatTime(show.show_time!)}</td>
                    <td>{show.available_pair_count}</td>
                    <td>
                      <Link to={`/dj/shows/${show.id}`} className="btn-primary btn-sm">
                        Give Away
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="shows-grid">
          {sortedShows.map((show) => {
            const noPairs = show.available_pair_count === 0;
            const hasAssignment = assignedShowIds.has(show.id);
            return (
              <div
                key={show.id}
                className={`show-card${noPairs ? ' show-card-dimmed' : ''}${hasAssignment ? ' show-card-has-assignment' : ''}${show.co_announce ? ' show-card-co-announce' : ''}`}
                title={noPairs ? 'No pass pairs available for this show' : undefined}
              >
                <div className="show-card-header">
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.4rem', flexWrap: 'wrap', flex: 1 }}>
                    <h3 style={{ margin: 0 }}><EnrichedShowName eventName={show.event_name} bands={show.bands ?? []} onGenreClick={(g) => setSelectedGenre(currentGenre ? currentGenre + ', ' + g : g)} /></h3>
                    {show.co_announce && (
                      <span className="co-announce-badge">📢 Co-Announce</span>
                    )}
                    {show.in_feature_bin && <FeatureBinBadge releases={show.feature_bin_releases} />}
                  </div>
                  <span className="show-genre-list">
                    {(show.genre ?? []).map((g) => (
                      <span
                        key={g}
                        className="show-genre show-genre-clickable"
                        onClick={() => setSelectedGenre(g)}
                        title="Click to filter by this genre"
                      >
                        {g}
                      </span>
                    ))}
                  </span>
                </div>

                <div className="show-card-body">
                  <div className="show-card-details">
                    <div className="info-row">
                      <span className="info-label">Venue:</span>
                      <span className="info-value">{show.venue.name}</span>
                    </div>
                    <div className="info-row">
                      <span className="info-label">{show.show_start_date ? 'Dates:' : 'Date:'}</span>
                      <span className="info-value">{show.show_start_date ? formatDateRange(show.show_start_date, show.show_date) : formatDate(show.show_date)}</span>
                    </div>
                    {!show.show_start_date && (
                    <div className="info-row">
                      <span className="info-label">Time:</span>
                      <span className="info-value">{formatTime(show.show_time!)}</span>
                    </div>
                    )}
                    <div className="info-row">
                      <span className="info-label">Age:</span>
                      <span className="info-value">{formatAgeRestriction(show.age_restriction)}</span>
                    </div>
                    <div className="info-row">
                      <span className="info-label">Accessible:</span>
                      <span className="info-value">
                        {show.wheelchair_accessible ? 'Yes' : 'No'}
                      </span>
                    </div>
                  </div>

                  <div className="pass-availability">
                    <div className="availability-badge">
                      <span className="badge-label">
                        Pass Pairs Available:
                        <Tooltip text="Each pass pair admits 2 people to the show. You give away one pair per winner." />
                      </span>
                      <span className="badge-count">{show.available_pair_count}</span>
                    </div>
                  </div>

                  {hasAssignment && (
                    <div className="show-card-assignment-hint">
                      ★ You have passes pre-assigned for this show
                    </div>
                  )}
                </div>

                <div className="show-card-footer">
                  <Link to={`/dj/shows/${show.id}`} className="btn-primary">
                    Give Away Passes
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default ShowBrowser;
