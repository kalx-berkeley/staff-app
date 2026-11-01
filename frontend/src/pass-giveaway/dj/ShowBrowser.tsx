import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { showsAPI, passesAPI } from '../api';
import SearchBar from '../promotions/SearchBar';
import { Tooltip, DjNameInput, DJ_NAME_KEY, EnrichedShowName, FeatureBinBadge, KalxLiveBadge, DatePicker } from '../components';
import type { ShowSummary, PassResponse } from '../types';
import type { APIError } from '../../common/types';
import { usePageTitle } from '../../common/hooks/usePageTitle';
import { WHEELCHAIR_ACCESSIBLE_LABELS, formatShowRating, isMovieShow } from '../utils';

const VIEW_MODE_KEY = 'kalx_dj_view_mode';

const getDefaultDateFrom = (): string => {
  const d = new Date();
  d.setDate(d.getDate() - 30);
  return d.toISOString().split('T')[0];
};

const getLocalTodayStr = (): string => {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
};

const ShowBrowser = () => {
  usePageTitle('Shows · DJ');
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
  // Bumped to re-fetch the DJ's pre-assigned passes after Clothespin or a release.
  const [assignedRefresh, setAssignedRefresh] = useState(0);
  const [clothespinShowId, setClothespinShowId] = useState<number | null>(null);
  const [releasePassId, setReleasePassId] = useState<number | null>(null);
  const [actionMessage, setActionMessage] = useState<{ kind: 'success' | 'error'; text: string } | null>(null);

  // A success message clears itself after a few seconds; an error stays until the next action.
  useEffect(() => {
    if (actionMessage?.kind !== 'success') return;
    const timer = setTimeout(() => setActionMessage(null), 4000);
    return () => clearTimeout(timer);
  }, [actionMessage]);

  // `silent` refreshes the list in place, without the loading screen, after
  // Clothespin or a release changes which shows still have unclaimed pairs.
  const loadShows = async ({ silent = false }: { silent?: boolean } = {}) => {
    try {
      if (!silent) setLoading(true);
      setError(null);
      const params = {
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      };
      const data = await showsAPI.list(params);
      const publishedOnly = data.filter((show) => show.status === 'published');
      setRawShows(publishedOnly);
    } catch (err) {
      if (silent) return;
      const apiError = err as APIError;
      setError(
        typeof apiError.detail === 'string' ? apiError.detail : 'Failed to load shows'
      );
    } finally {
      if (!silent) setLoading(false);
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
  }, [djName, assignedRefresh]);

  const handleViewMode = (mode: 'card' | 'compact') => {
    setViewMode(mode);
    localStorage.setItem(VIEW_MODE_KEY, mode);
  };

  const assignedShowIds = new Set(myAssignedPasses.map((p) => p.show_id));
  const myPairCountByShow = new Map<number, number>();
  for (const p of myAssignedPasses) {
    myPairCountByShow.set(p.show_id, (myPairCountByShow.get(p.show_id) ?? 0) + 1);
  }
  // The pairs this DJ can give away: the ones no DJ has, plus their own.
  // The rest of the available pairs are pre-assigned to other DJs.
  const pairCounts = (show: ShowSummary) => {
    const yours = Math.min(
      show.unassigned_pair_count + (myPairCountByShow.get(show.id) ?? 0),
      show.available_pair_count
    );
    return { yours, reservedForOthers: show.available_pair_count - yours };
  };
  const reservedLabel = (count: number) =>
    `${count} pre-assigned to ${djName.trim() ? 'other DJs' : 'DJs'}`;
  const todayStr = getLocalTodayStr();
  const assignedTodayShowIds = new Set(
    myAssignedPasses.filter((p) => p.preassigned_date === todayStr).map((p) => p.show_id)
  );

  // Clothespin needs a DJ name, a show whose rules allow it with an unclaimed
  // pair left, and no pair already reserved for this DJ for today.
  const canClothespin = (show: ShowSummary) =>
    !!djName.trim() && show.clothespin_available && !assignedTodayShowIds.has(show.id);

  const apiErrorText = (err: unknown, fallback: string) => {
    const detail = (err as APIError).detail;
    return typeof detail === 'string' ? detail : fallback;
  };

  const handleClothespin = async (show: ShowSummary) => {
    const name = djName.trim();
    setClothespinShowId(show.id);
    setActionMessage(null);
    try {
      const pass = await passesAPI.clothespin(show.id, name);
      setActionMessage({
        kind: 'success',
        text: `Reserved a pass pair for ${show.event_name} for ${pass.preassigned_dj ?? name} today.`,
      });
      setAssignedRefresh((n) => n + 1);
      await loadShows({ silent: true });
    } catch (err) {
      setActionMessage({ kind: 'error', text: apiErrorText(err, 'Failed to reserve a pass pair') });
    } finally {
      setClothespinShowId(null);
    }
  };

  const handleRelease = async (pass: PassResponse) => {
    const showName = pass.show_event_name || 'this show';
    if (!window.confirm(`Release your reserved pass pair for ${showName}? Any DJ could then give it away.`)) {
      return;
    }
    setReleasePassId(pass.id);
    setActionMessage(null);
    try {
      await passesAPI.removePreassignment(pass.id, djName.trim());
      setActionMessage({ kind: 'success', text: `Released your pass pair for ${showName}.` });
      setAssignedRefresh((n) => n + 1);
      await loadShows({ silent: true });
    } catch (err) {
      setActionMessage({ kind: 'error', text: apiErrorText(err, 'Failed to release the reservation') });
    } finally {
      setReleasePassId(null);
    }
  };

  const clothespinTitle = "Reserve one pass pair under your DJ name for today's on-air giveaway";

  const renderClothespinButton = (show: ShowSummary, small: boolean) =>
    canClothespin(show) && (
      <button
        type="button"
        className={small ? 'btn-secondary btn-small' : 'btn-secondary'}
        onClick={() => handleClothespin(show)}
        disabled={clothespinShowId !== null}
        title={clothespinTitle}
        aria-label={`Clothespin a pass pair for ${show.event_name}`}
      >
        {clothespinShowId === show.id ? 'Reserving…' : 'Clothespin'}
      </button>
    );

  const renderReleaseButton = (pass: PassResponse, small: boolean) => (
    <button
      type="button"
      className={small ? 'btn-danger btn-small' : 'btn-danger'}
      onClick={() => handleRelease(pass)}
      disabled={releasePassId !== null}
      title="Remove this reservation so the pass pair becomes available to any DJ"
      aria-label={`Release reservation for ${pass.show_event_name || 'this show'}`}
    >
      {releasePassId === pass.id ? 'Releasing…' : 'Release Reservation'}
    </button>
  );

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

      {actionMessage && (
        <div
          className={`dj-action-message ${actionMessage.kind === 'success' ? 'success-message' : 'error-message'}`}
          role={actionMessage.kind === 'success' ? 'status' : 'alert'}
        >
          {actionMessage.text}
        </div>
      )}

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
                    {myAssignedPasses.map((pass) => {
                      const isAirdateToday = pass.preassigned_date === getLocalTodayStr();
                      return (
                        <tr key={pass.id} className={isAirdateToday ? 'has-assignment' : 'show-dimmed'}>
                          <td>{pass.show_event_name || '—'}</td>
                          <td>{pass.show_venue_name || '—'}</td>
                          <td>{pass.show_date ? formatDateShort(pass.show_date) : '—'}</td>
                          <td>{pass.preassigned_date ? formatDateShort(pass.preassigned_date) : '—'}</td>
                          <td>
                            <div className="show-row-actions">
                              <Link to={`/dj/shows/${pass.show_id}`} className="btn-primary btn-small">
                                Give Away Passes
                              </Link>
                              {renderReleaseButton(pass, true)}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="shows-grid">
                {myAssignedPasses.map((pass) => {
                  const isAirdateToday = pass.preassigned_date === getLocalTodayStr();
                  return (
                  <div key={pass.id} className={`show-card${isAirdateToday ? ' show-card-assigned' : ' show-card-assigned-inactive'}`}>
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

                    <div className="show-card-footer show-card-actions">
                      <Link to={`/dj/shows/${pass.show_id}`} className="btn-primary">
                        Give Away Passes
                      </Link>
                      {renderReleaseButton(pass, false)}
                    </div>
                  </div>
                  );
                })}
              </div>
            )
          )}
        </div>
      )}

      {error ? (
        <div className="error">
          <p>Error: {error}</p>
          <button onClick={() => loadShows()} className="btn-primary">
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
                  <Tooltip text="Pass pairs you can give away on air. Pairs pre-assigned to other DJs aren't counted." />
                </th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sortedShows.map((show) => {
                const { yours, reservedForOthers } = pairCounts(show);
                const noPairs = yours === 0;
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
                      {show.on_kalx_live && (
                        <span style={{ marginLeft: '0.5rem' }}>
                          <KalxLiveBadge appearances={show.kalx_live_appearances} />
                        </span>
                      )}
                    </td>
                    <td>{show.venue.name}</td>
                    <td>{show.show_start_date ? formatDateRange(show.show_start_date, show.show_date) : formatDateShort(show.show_date)}</td>
                    <td>{show.show_start_date ? '—' : formatTime(show.show_time!)}</td>
                    <td>
                      {yours}
                      {reservedForOthers > 0 && (
                        <span className="pairs-reserved-note" title={reservedLabel(reservedForOthers)}> ({reservedForOthers} pre-assigned)</span>
                      )}
                    </td>
                    <td>
                      <div className="show-row-actions">
                        {noPairs ? (
                          <Link to={`/dj/shows/${show.id}`} className="btn-secondary btn-small">
                            View
                          </Link>
                        ) : (
                          <Link to={`/dj/shows/${show.id}`} className="btn-primary btn-small">
                            Give Away
                          </Link>
                        )}
                        {renderClothespinButton(show, true)}
                      </div>
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
            const { yours, reservedForOthers } = pairCounts(show);
            const noPairs = yours === 0;
            const hasAssignment = assignedShowIds.has(show.id);
            return (
              <div
                key={show.id}
                className={`show-card${noPairs ? ' show-card-dimmed' : ''}${hasAssignment ? ' show-card-has-assignment' : ''}${show.co_announce ? ' show-card-co-announce' : ''}`}
                title={
                  !noPairs
                    ? undefined
                    : reservedForOthers > 0
                      ? 'Every pass pair left is pre-assigned to another DJ'
                      : 'No pass pairs available for this show'
                }
              >
                <div className="show-card-header">
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.4rem', flexWrap: 'wrap', flex: 1 }}>
                    <h3 style={{ margin: 0 }}><EnrichedShowName eventName={show.event_name} bands={show.bands ?? []} onGenreClick={(g) => setSelectedGenre(currentGenre ? currentGenre + ', ' + g : g)} /></h3>
                    {show.co_announce && (
                      <span className="co-announce-badge">📢 Co-Announce</span>
                    )}
                    {show.in_feature_bin && <FeatureBinBadge releases={show.feature_bin_releases} />}
                    {show.on_kalx_live && <KalxLiveBadge appearances={show.kalx_live_appearances} />}
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
                      <span className="info-label">{isMovieShow(show) ? 'Rating:' : 'Age:'}</span>
                      <span className="info-value">{formatShowRating(show)}</span>
                    </div>
                    <div className="info-row">
                      <span className="info-label">Accessible:</span>
                      <span className="info-value">
                        {WHEELCHAIR_ACCESSIBLE_LABELS[show.wheelchair_accessible]}
                      </span>
                    </div>
                  </div>

                  <div className="pass-availability">
                    <div className="availability-badge">
                      <span className="badge-label">
                        Pass Pairs Available:
                        <Tooltip text="Each pass pair admits 2 people to the show. You give away one pair per winner. Pairs pre-assigned to other DJs aren't counted." />
                      </span>
                      <span className="badge-count">{yours}</span>
                    </div>
                    {reservedForOthers > 0 && (
                      <div className="pairs-reserved-note">{reservedLabel(reservedForOthers)}</div>
                    )}
                  </div>

                  {hasAssignment && (
                    <div className="show-card-assignment-hint">
                      ★ You have passes pre-assigned for this show
                    </div>
                  )}
                </div>

                <div className="show-card-footer show-card-actions">
                  {noPairs ? (
                    <Link to={`/dj/shows/${show.id}`} className="btn-secondary">
                      View Show
                    </Link>
                  ) : (
                    <Link to={`/dj/shows/${show.id}`} className="btn-primary">
                      Give Away Passes
                    </Link>
                  )}
                  {renderClothespinButton(show, false)}
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
