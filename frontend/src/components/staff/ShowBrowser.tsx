import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { showsAPI } from '../../services/api';
import SearchBar from '../promotions/SearchBar';
import { Tooltip, EnrichedShowName } from '../shared';
import type { ShowSummary, APIError } from '../../types';

const VIEW_MODE_KEY = 'kalx_staff_view_mode';

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
  const [statusFilter, setStatusFilter] = useState<'all' | 'published'>('published');
  const [sortBy, setSortBy] = useState<'date' | 'band' | 'venue' | 'published'>('date');
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
      const nonDraft = data.filter((show) => show.status !== 'draft');
      setRawShows(nonDraft);
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

  const handleViewMode = (mode: 'card' | 'compact') => {
    setViewMode(mode);
    localStorage.setItem(VIEW_MODE_KEY, mode);
  };

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

  const statusFiltered =
    statusFilter === 'all'
      ? filteredShows
      : filteredShows.filter((show) => show.status === 'published');

  const sortedShows = [...statusFiltered].sort((a, b) => {
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

  if (loading) {
    return <div className="loading">Loading shows...</div>;
  }

  if (error) {
    return (
      <div className="error">
        <p>Error: {error}</p>
        <button onClick={loadShows} className="btn-primary">
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="show-browser">
      <div className="page-header">
        <h2>Available Shows</h2>
        <p className="page-description">
          Browse published shows and claim staff passes
        </p>
      </div>

      <SearchBar shows={allShows} onSearch={setFilteredShows} externalGenre={selectedGenre} onGenreChange={setCurrentGenre} />

      <div className="sort-controls">
        <span className="label-with-help" style={{ display: 'inline-flex' }}>
          <span>Filter by status:</span>
          <Tooltip text="Published Shows: only active shows where staff passes can still be claimed. All Shows: includes closed shows where passes are no longer available." />
        </span>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as 'all' | 'published')}
        >
          <option value="published">Published Shows</option>
          <option value="all">All Shows</option>
        </select>

        <label htmlFor="staff-sort-by" style={{ marginLeft: '1rem' }}>Sort by:</label>
        <select
          id="staff-sort-by"
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as 'date' | 'band' | 'venue' | 'published')}
        >
          <option value="date">Date (soonest first)</option>
          <option value="band">Band name</option>
          <option value="venue">Venue name</option>
          <option value="published">Published (newest first)</option>
        </select>

        <span style={{ marginLeft: '1rem' }}>
          <label htmlFor="staff-date-from">From:</label>{' '}
          <input
            type="date"
            id="staff-date-from"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            style={{ fontSize: '0.9rem' }}
          />
        </span>
        <span style={{ marginLeft: '0.5rem' }}>
          <label htmlFor="staff-date-to">To:</label>{' '}
          <input
            type="date"
            id="staff-date-to"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
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

      {sortedShows.length === 0 ? (
        <div className="no-shows">
          <p>{statusFilter === 'published' ? 'No published shows available at this time.' : 'No shows available at this time.'}</p>
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
                  Staff Passes
                  <Tooltip text="Available staff passes for this show" />
                </th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sortedShows.map((show) => {
                const guestHoldCount = show.guest_hold_staff_count;
                const adjustedAvailableCount = show.available_staff_count + guestHoldCount;
                const hasClaimable = adjustedAvailableCount > 0;
                const noPasses = !hasClaimable;
                const isClosed = show.status === 'closed';
                const rowClass = [noPasses ? 'show-dimmed' : '', isClosed ? 'show-row-closed' : ''].filter(Boolean).join(' ');
                const passCountDisplay = String(adjustedAvailableCount);
                return (
                  <tr key={show.id} className={[rowClass, show.co_announce ? 'show-row-co-announce' : ''].filter(Boolean).join(' ') || undefined}>
                    <td>
                      <EnrichedShowName eventName={show.event_name} bands={show.bands ?? []} onGenreClick={(g) => setSelectedGenre(currentGenre ? currentGenre + ', ' + g : g)} />
                      {isClosed && <span className="status-badge status-closed" style={{ marginLeft: '0.5rem', fontSize: '0.7rem', verticalAlign: 'middle' }}>Closed</span>}
                      {show.co_announce && (
                        <span className="co-announce-badge" style={{ marginLeft: '0.5rem' }}>📢 Co-Announce</span>
                      )}
                    </td>
                    <td>{show.venue.name}</td>
                    <td>{show.show_start_date ? formatDateRange(show.show_start_date, show.show_date) : formatDateShort(show.show_date)}</td>
                    <td>{show.show_start_date ? '—' : formatTime(show.show_time!)}</td>
                    <td>{passCountDisplay}</td>
                    <td>
                      <Link to={`/staff/shows/${show.id}`} className="btn-primary btn-sm">
                        View Details
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
            const guestHoldCount = show.guest_hold_staff_count;
            const adjustedAvailableCount = show.available_staff_count + guestHoldCount;
            const hasClaimable = adjustedAvailableCount > 0;
            const noPasses = !hasClaimable;
            const isClosed = show.status === 'closed';
            const cardClass = ['show-card', noPasses ? 'show-card-dimmed' : '', isClosed ? 'show-card-closed' : '', show.co_announce ? 'show-card-co-announce' : ''].filter(Boolean).join(' ');
            const passCountDisplay = String(adjustedAvailableCount);
            const cardTitle = noPasses ? 'No staff passes available for this show' : undefined;
            return (
              <div
                key={show.id}
                className={cardClass}
                title={cardTitle}
              >
                <div className="show-card-header">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <h3 style={{ margin: 0 }}><EnrichedShowName eventName={show.event_name} bands={show.bands ?? []} onGenreClick={(g) => setSelectedGenre(currentGenre ? currentGenre + ', ' + g : g)} /></h3>
                    {isClosed && <span className="status-badge status-closed">Closed</span>}
                    {show.co_announce && <span className="co-announce-badge">📢 Co-Announce</span>}
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
                        Staff Passes Available:
                        <Tooltip text="Staff passes let you attend the show. Claim one to reserve your spot — each pass admits 1 person." />
                      </span>
                      <span className="badge-count">{passCountDisplay}</span>
                    </div>
                  </div>
                </div>

                <div className="show-card-footer">
                  <Link to={`/staff/shows/${show.id}`} className="btn-primary">
                    View Details
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
