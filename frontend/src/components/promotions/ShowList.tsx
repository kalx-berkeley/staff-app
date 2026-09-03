import { useState, useEffect, useCallback, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { showsAPI } from '../../services/api';
import type { ShowSummary, ShowStatus, APIError } from '../../types';
import SearchBar from './SearchBar';
import { Tooltip, EnrichedShowName } from '../shared';

type SortBy = 'date' | 'band' | 'venue' | 'published';

const VIEW_MODE_KEY = 'kalx_promo_view_mode';

const getDefaultDateFrom = (): string => {
  const d = new Date();
  d.setDate(d.getDate() - 30);
  return d.toISOString().split('T')[0];
};

const ShowList = () => {
  const [allShows, setAllShows] = useState<ShowSummary[]>([]);
  const [searchResults, setSearchResults] = useState<ShowSummary[]>([]);
  const [showMineOnly, setShowMineOnly] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<ShowStatus | 'all'>('published');
  const [selectedGenre, setSelectedGenre] = useState('');
  const [currentGenre, setCurrentGenre] = useState('');
  const [sortBy, setSortBy] = useState<SortBy>('date');
  const [viewMode, setViewMode] = useState<'card' | 'compact'>(
    (localStorage.getItem(VIEW_MODE_KEY) as 'card' | 'compact') || 'card'
  );
  const [dateFrom, setDateFrom] = useState(getDefaultDateFrom());
  const [dateTo, setDateTo] = useState('');

  const baseShows = useMemo(
    () => showMineOnly ? allShows.filter((s) => s.is_mine) : allShows,
    [showMineOnly, allShows]
  );

  const loadShows = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const params = {
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      };
      const data = await showsAPI.list(params);
      setAllShows(data);
    } catch (err) {
      const apiError = err as APIError;
      setError(
        typeof apiError.detail === 'string' ? apiError.detail : 'Failed to load shows'
      );
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo]);

  useEffect(() => {
    loadShows();
  }, [loadShows]);

  const handleViewMode = (mode: 'card' | 'compact') => {
    setViewMode(mode);
    localStorage.setItem(VIEW_MODE_KEY, mode);
  };

  const statusFiltered =
    statusFilter === 'all'
      ? searchResults
      : searchResults.filter((show) => show.status === statusFilter);

  const filteredShows = statusFiltered;

  const getStatusBadgeClass = (status: ShowStatus): string => {
    switch (status) {
      case 'draft':
        return 'status-badge status-draft';
      case 'published':
        return 'status-badge status-published';
      case 'closed':
        return 'status-badge status-closed';
      default:
        return 'status-badge';
    }
  };

  const formatDate = (dateStr: string): string => {
    const [_y, _m, _d] = dateStr.split('-').map(Number); const date = new Date(_y, _m - 1, _d);
    return date.toLocaleDateString('en-US', {
      weekday: 'short',
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const formatDateShort = (dateStr: string): string => {
    const [_y, _m, _d] = dateStr.split('-').map(Number); const date = new Date(_y, _m - 1, _d);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const formatTime = (timeStr: string): string => {
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
    <div className="show-list">
      <div className="show-list-header">
        <h2>Shows</h2>
        <div className="mine-toggle">
          <button
            className={showMineOnly ? 'btn-primary' : 'btn-secondary'}
            onClick={() => setShowMineOnly(true)}
            title="Show only shows at venues where you are listed as an owner"
          >
            My Shows
          </button>
          <button
            className={!showMineOnly ? 'btn-primary' : 'btn-secondary'}
            onClick={() => setShowMineOnly(false)}
            title="Show all shows in the system"
          >
            All Shows
          </button>
        </div>
        <Link to="/promotions/shows/new" className="btn-primary">
          Create New Show
        </Link>
      </div>

      <SearchBar shows={baseShows} onSearch={setSearchResults} externalGenre={selectedGenre} onGenreChange={setCurrentGenre} />

      <div className="status-filter">
        <span className="label-with-help" style={{ display: 'inline-flex' }}>
          <span>Filter by status:</span>
          <Tooltip text="Draft: not yet visible to DJs. Published: active, DJs can give away passes. Closed: show is complete, no further giveaways." />
        </span>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as ShowStatus | 'all')}
        >
          <option value="all">All Shows</option>
          <option value="draft">Draft</option>
          <option value="published">Published</option>
          <option value="closed">Closed</option>
        </select>

        <label htmlFor="promo-sort-by" style={{ marginLeft: '1rem' }}>Sort by:</label>
        <select
          id="promo-sort-by"
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as SortBy)}
        >
          <option value="date">Date (soonest first)</option>
          <option value="band">Band name</option>
          <option value="venue">Venue name</option>
          <option value="published">Published (newest first)</option>
        </select>

        <span style={{ marginLeft: '1rem' }}>
          <label htmlFor="promo-date-from">From:</label>{' '}
          <input
            type="date"
            id="promo-date-from"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            style={{ fontSize: '0.9rem' }}
          />
        </span>
        <span style={{ marginLeft: '0.5rem' }}>
          <label htmlFor="promo-date-to">To:</label>{' '}
          <input
            type="date"
            id="promo-date-to"
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

      {error ? (
        <div className="error">
          <p>Error: {error}</p>
          <button onClick={loadShows}>Retry</button>
        </div>
      ) : loading ? (
        <div className="loading">Loading shows...</div>
      ) : sortedShows.length === 0 ? (
        <p className="empty-message">
          {statusFilter === 'all'
            ? 'No shows found. Create your first show!'
            : `No ${statusFilter} shows found.`}
        </p>
      ) : viewMode === 'compact' ? (
        <div className="shows-list">
          <table className="shows-list-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Event</th>
                <th>Venue</th>
                <th>Date</th>
                <th title="Available / total on-air giveaway pairs">Pairs</th>
                <th title="Available / total staff passes">Staff</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sortedShows.map((show) => (
                <tr key={show.id} className={show.co_announce ? 'show-row-co-announce' : undefined}>
                  <td>
                    <span className={getStatusBadgeClass(show.status)}>{show.status}</span>
                  </td>
                  <td>
                    <EnrichedShowName eventName={show.event_name} bands={show.bands ?? []} onGenreClick={(g) => setSelectedGenre(currentGenre ? currentGenre + ', ' + g : g)} />
                    {show.co_announce && (
                      <span className="co-announce-badge" style={{ marginLeft: '0.5rem' }}>📢 Co-Announce</span>
                    )}
                  </td>
                  <td>{show.venue.name}</td>
                  <td>{show.show_start_date ? formatDateRange(show.show_start_date, show.show_date) : formatDateShort(show.show_date)}</td>
                  <td>{show.available_pair_count}/{show.num_pass_pairs}</td>
                  <td>{show.available_staff_count}/{show.num_pass_pairs}</td>
                  <td>
                    <Link to={`/promotions/shows/${show.id}`} className="btn-primary btn-small">
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="show-grid">
          {sortedShows.map((show) => (
            <div
              key={show.id}
              className={`show-card${show.co_announce ? ' show-card-co-announce' : ''}`}
            >
              <div className="show-card-header">
                <h3><EnrichedShowName eventName={show.event_name} bands={show.bands ?? []} /></h3>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap' }}>
                  {show.co_announce && (
                    <span className="co-announce-badge">📢 Co-Announce</span>
                  )}
                  <span className={getStatusBadgeClass(show.status)}>
                    {show.status}
                  </span>
                </div>
              </div>
              <div className="show-card-body">
                <p className="show-venue">{show.venue.name}</p>
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
                <p className="show-date">
                  {show.show_start_date
                    ? formatDateRange(show.show_start_date, show.show_date)
                    : `${formatDate(show.show_date)} at ${formatTime(show.show_time!)}`}
                </p>
                <div className="show-passes">
                  <span title="Available / total on-air giveaway pairs (each pair admits 2 people)">
                    Pass Pairs: {show.available_pair_count}/{show.num_pass_pairs}
                  </span>
                  <span title="Available / total staff passes (one per staff member)">
                    Staff Passes: {show.available_staff_count}/{show.num_pass_pairs}
                  </span>
                </div>
              </div>
              <div className="show-card-footer">
                <Link to={`/promotions/shows/${show.id}`} className="btn-primary">
                  View Show
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ShowList;
