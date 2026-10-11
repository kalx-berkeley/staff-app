import { useState, useEffect } from 'react';
import { adminAPI, showsAPI, venuesAPI } from '../api';
import type { SeedResult, AutoCloseScheduleItem, LotteryScheduleItem, ShowResponse, VenueResponse } from '../types';
import type { APIError } from '../../common/types';
import { useAuth } from '../../common/contexts/authHooks';
import { usePageTitle } from '../../common/hooks/usePageTitle';
import { subsiteForPath } from '../../subsites';

const Admin = () => {
  usePageTitle('Admin · Promotions');
  const { user } = useAuth();
  const isStaging = user?.is_staging ?? false;
  const staffAdmin = subsiteForPath('/admin');

  const [seeding, setSeeding] = useState(false);
  const [seedResult, setSeedResult] = useState<SeedResult | null>(null);
  const [seedError, setSeedError] = useState<string | null>(null);
  const [seedAlreadyLoaded, setSeedAlreadyLoaded] = useState(false);

  const [deletedShows, setDeletedShows] = useState<ShowResponse[]>([]);
  const [deletedShowsLoading, setDeletedShowsLoading] = useState(true);
  const [deletedShowsError, setDeletedShowsError] = useState<string | null>(null);
  const [undeleting, setUndeleting] = useState<Record<number, boolean>>({});

  const [deletedVenues, setDeletedVenues] = useState<VenueResponse[]>([]);
  const [deletedVenuesLoading, setDeletedVenuesLoading] = useState(true);
  const [deletedVenuesError, setDeletedVenuesError] = useState<string | null>(null);
  const [undeletingVenue, setUndeletingVenue] = useState<Record<number, boolean>>({});

  const [autoCloseSchedules, setAutoCloseSchedules] = useState<AutoCloseScheduleItem[]>([]);
  const [autoCloseLoading, setAutoCloseLoading] = useState(true);
  const [autoCloseError, setAutoCloseError] = useState<string | null>(null);
  const [hideClosedAutoClose, setHideClosedAutoClose] = useState(true);

  const [lotterySchedules, setLotterySchedules] = useState<LotteryScheduleItem[]>([]);
  const [lotterySchedulesLoading, setLotterySchedulesLoading] = useState(true);
  const [lotterySchedulesError, setLotterySchedulesError] = useState<string | null>(null);
  const [lotteryRunning, setLotteryRunning] = useState<Record<number, boolean>>({});
  const [lotteryRunResult, setLotteryRunResult] = useState<Record<number, string | null>>({});

  const loadDeletedShows = () => {
    setDeletedShowsLoading(true);
    setDeletedShowsError(null);
    showsAPI
      .listDeleted()
      .then(setDeletedShows)
      .catch((err) => {
        const apiError = err as APIError;
        setDeletedShowsError(
          typeof apiError.detail === 'string' ? apiError.detail : 'Failed to load deleted shows'
        );
      })
      .finally(() => setDeletedShowsLoading(false));
  };

  const handleUndelete = async (showId: number) => {
    setUndeleting((prev) => ({ ...prev, [showId]: true }));
    try {
      await showsAPI.undelete(showId);
      setDeletedShows((prev) => prev.filter((s) => s.id !== showId));
    } catch (err) {
      const apiError = err as APIError;
      setDeletedShowsError(
        typeof apiError.detail === 'string' ? apiError.detail : 'Failed to restore show'
      );
    } finally {
      setUndeleting((prev) => ({ ...prev, [showId]: false }));
    }
  };

  const loadDeletedVenues = () => {
    setDeletedVenuesLoading(true);
    setDeletedVenuesError(null);
    venuesAPI
      .listDeleted()
      .then(setDeletedVenues)
      .catch((err) => {
        const apiError = err as APIError;
        setDeletedVenuesError(
          typeof apiError.detail === 'string' ? apiError.detail : 'Failed to load deleted venues'
        );
      })
      .finally(() => setDeletedVenuesLoading(false));
  };

  const handleUndeleteVenue = async (venueId: number) => {
    setUndeletingVenue((prev) => ({ ...prev, [venueId]: true }));
    try {
      await venuesAPI.undelete(venueId);
      setDeletedVenues((prev) => prev.filter((v) => v.id !== venueId));
    } catch (err) {
      const apiError = err as APIError;
      setDeletedVenuesError(
        typeof apiError.detail === 'string' ? apiError.detail : 'Failed to restore venue'
      );
    } finally {
      setUndeletingVenue((prev) => ({ ...prev, [venueId]: false }));
    }
  };

  useEffect(() => {
    loadDeletedShows();
    loadDeletedVenues();
    adminAPI.getAutoCloseSchedules()
      .then(setAutoCloseSchedules)
      .catch((err) => {
        const apiError = err as APIError;
        setAutoCloseError(
          typeof apiError.detail === 'string' ? apiError.detail : 'Failed to load auto-close schedules'
        );
      })
      .finally(() => setAutoCloseLoading(false));
    adminAPI.getLotterySchedules()
      .then(setLotterySchedules)
      .catch((err) => {
        const apiError = err as APIError;
        setLotterySchedulesError(
          typeof apiError.detail === 'string' ? apiError.detail : 'Failed to load lottery schedules'
        );
      })
      .finally(() => setLotterySchedulesLoading(false));
    if (isStaging) {
      adminAPI.getSeedStatus().then((s) => setSeedAlreadyLoaded(s.seeded)).catch(() => {});
    }
  }, [isStaging]);

  const handleSeed = async () => {
    setSeeding(true);
    setSeedResult(null);
    setSeedError(null);
    try {
      const result = await adminAPI.seedTestData();
      setSeedResult(result);
      if (result.venues_added > 0 || result.shows_added > 0) {
        setSeedAlreadyLoaded(true);
      }
    } catch (err) {
      const apiError = err as APIError;
      setSeedError(
        typeof apiError.detail === 'string' ? apiError.detail : 'Seed failed'
      );
    } finally {
      setSeeding(false);
    }
  };

  const handleRunLottery = async (showId: number) => {
    setLotteryRunning((prev) => ({ ...prev, [showId]: true }));
    setLotteryRunResult((prev) => ({ ...prev, [showId]: null }));
    try {
      const result = await adminAPI.runLottery(showId);
      setLotteryRunResult((prev) => ({ ...prev, [showId]: result.message }));
      const updated = await adminAPI.getLotterySchedules();
      setLotterySchedules(updated);
    } catch (err) {
      const apiError = err as APIError;
      setLotteryRunResult((prev) => ({
        ...prev,
        [showId]: typeof apiError.detail === 'string' ? apiError.detail : 'Failed to run lottery',
      }));
    } finally {
      setLotteryRunning((prev) => ({ ...prev, [showId]: false }));
    }
  };

  return (
    <div className="admin-container">
      <h2>Admin</h2>
      {staffAdmin?.isAvailable(user) && (
        <p className="field-hint">
          Scheduled jobs, the audit log and user impersonation are in{' '}
          <a href={`${staffAdmin.basePath}/`}>{staffAdmin.name}</a>.
        </p>
      )}

      <section className="admin-section">
        <h3>Auto-close Schedules</h3>
        <p className="field-hint">
          Shows with auto-close enabled and their scheduled close times (Pacific Time).
        </p>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', marginBottom: '0.75rem' }}>
          <input
            type="checkbox"
            checked={hideClosedAutoClose}
            onChange={(e) => setHideClosedAutoClose(e.target.checked)}
          />
          Hide already closed shows
        </label>
        {autoCloseLoading ? (
          <p>Loading…</p>
        ) : autoCloseError ? (
          <div className="error-message">{autoCloseError}</div>
        ) : autoCloseSchedules.length === 0 ? (
          <p className="field-hint">No auto-close schedules configured.</p>
        ) : (() => {
          const visibleAutoCloseSchedules = hideClosedAutoClose
            ? autoCloseSchedules.filter((item) => item.show_status !== 'closed')
            : autoCloseSchedules;
          return visibleAutoCloseSchedules.length === 0 ? (
            <p className="field-hint">No auto-close schedules to show.</p>
          ) : (
          <div className="scrollable-table-wrapper">
            <table className="audit-log-table">
              <thead>
                <tr>
                  <th>Show</th>
                  <th>Venue</th>
                  <th>Planned Close (PT)</th>
                  <th>Show Status</th>
                  <th>Schedule Status</th>
                </tr>
              </thead>
              <tbody>
                {visibleAutoCloseSchedules.map((item) => (
                  <tr key={item.show_id}>
                    <td>
                      <a href={`/pass-giveaway/promotions/shows/${item.show_id}`}>
                        {item.event_name}
                      </a>
                    </td>
                    <td>{item.venue_name}</td>
                    <td className="audit-log-time">
                      {item.planned_close_date} {item.planned_close_time}
                    </td>
                    <td>
                      <span className={`status-badge status-${item.show_status}`}>
                        {item.show_status}
                      </span>
                    </td>
                    <td>
                      <span
                        className={`status-badge${
                          item.schedule_status === 'scheduled'
                            ? ' status-published'
                            : item.schedule_status === 'executed'
                            ? ' status-closed'
                            : ''
                        }`}
                      >
                        {item.schedule_status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          );
        })()}
      </section>

      <section className="admin-section">
        <h3>Lottery Schedules</h3>
        <p className="field-hint">
          Shows with lottery enabled and their current lottery status.
        </p>
        {lotterySchedulesLoading ? (
          <p>Loading…</p>
        ) : lotterySchedulesError ? (
          <div className="error-message">{lotterySchedulesError}</div>
        ) : lotterySchedules.length === 0 ? (
          <p className="field-hint">No lottery-enabled shows.</p>
        ) : (
          <div className="scrollable-table-wrapper">
            <table className="audit-log-table">
              <thead>
                <tr>
                  <th>Show</th>
                  <th>Venue</th>
                  <th>Lottery Closes (PT)</th>
                  <th>Staff</th>
                  <th>DJs</th>
                  <th>Show Status</th>
                  <th>Lottery Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {lotterySchedules.map((item) => (
                <tr key={item.show_id}>
                  <td>
                    <a href={`/pass-giveaway/promotions/shows/${item.show_id}`}>
                      {item.event_name}
                    </a>
                  </td>
                  <td>{item.venue_name}</td>
                  <td className="audit-log-time">
                    {new Date(item.lottery_deadline).toLocaleString('en-US', {
                      timeZone: 'America/Los_Angeles',
                      month: 'short',
                      day: 'numeric',
                      hour: 'numeric',
                      minute: '2-digit',
                    })}
                  </td>
                  <td>{item.staff_entry_count}</td>
                  <td>{item.dj_entry_count}</td>
                  <td>
                    <span className={`status-badge status-${item.show_status}`}>
                      {item.show_status}
                    </span>
                  </td>
                  <td>
                    <span
                      className={`status-badge${
                        item.schedule_status === 'scheduled'
                          ? ' status-published'
                          : item.schedule_status === 'executed'
                          ? ' status-closed'
                          : ''
                      }`}
                    >
                      {item.schedule_status}
                    </span>
                  </td>
                  <td>
                    {item.schedule_status === 'scheduled' && (
                      <button
                        className="btn-primary btn-small"
                        onClick={() => handleRunLottery(item.show_id)}
                        disabled={!!lotteryRunning[item.show_id]}
                      >
                        {lotteryRunning[item.show_id] ? 'Running…' : 'Run Now'}
                      </button>
                    )}
                    {lotteryRunResult[item.show_id] && (
                      <span
                        className={
                          lotteryRunResult[item.show_id]?.startsWith('Failed') ||
                          lotteryRunResult[item.show_id]?.startsWith('Error')
                            ? 'error-message'
                            : 'text-success'
                        }
                        style={{ marginLeft: '0.5rem', fontSize: '0.85em' }}
                      >
                        {lotteryRunResult[item.show_id]}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {isStaging && (
        <>
          <section className={`admin-section${seedAlreadyLoaded ? ' admin-section--disabled' : ''}`}>
            <h3>Seed Test Data</h3>
            <p>
              Populate the database with test venues and shows from the CSV files
              in <code>backend/test_data/</code>. Existing records are skipped.
            </p>
            {seedAlreadyLoaded && (
              <p className="field-hint">Seed data has already been loaded.</p>
            )}
            <button
              className="btn-primary"
              onClick={handleSeed}
              disabled={seeding || seedAlreadyLoaded}
            >
              {seeding ? 'Seeding...' : 'Seed Test Data'}
            </button>
            {seedError && <div className="error-message">{seedError}</div>}
            {seedResult && (
              <div className="seed-result">
                <table className="seed-result-table">
                  <tbody>
                    <tr>
                      <td>Venues added</td>
                      <td>{seedResult.venues_added}</td>
                    </tr>
                    <tr>
                      <td>Venues skipped (already exist)</td>
                      <td>{seedResult.venues_skipped}</td>
                    </tr>
                    <tr>
                      <td>Shows added</td>
                      <td>{seedResult.shows_added}</td>
                    </tr>
                    <tr>
                      <td>Shows skipped (already exist)</td>
                      <td>{seedResult.shows_skipped}</td>
                    </tr>
                  </tbody>
                </table>
                {seedResult.errors.length > 0 && (
                  <div className="seed-errors">
                    <h4>Errors</h4>
                    <ul>
                      {seedResult.errors.map((e, i) => (
                        <li key={i}>{e}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </section>
        </>
      )}
      <section className="admin-section">
        <h3>Deleted Shows</h3>
        {deletedShowsLoading ? (
          <p>Loading deleted shows…</p>
        ) : deletedShowsError ? (
          <div className="error-message">{deletedShowsError}</div>
        ) : deletedShows.length === 0 ? (
          <p className="field-help">No deleted shows.</p>
        ) : (
          <table className="audit-log-table">
            <thead>
              <tr>
                <th>Show</th>
                <th>Venue</th>
                <th>Date</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {deletedShows.map((show) => (
                <tr key={show.id}>
                  <td>{show.event_name}</td>
                  <td>{show.venue.name}</td>
                  <td>{show.show_date}</td>
                  <td>
                    <button
                      className="btn-secondary"
                      onClick={() => handleUndelete(show.id)}
                      disabled={!!undeleting[show.id]}
                    >
                      {undeleting[show.id] ? 'Restoring…' : 'Restore to Draft'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="admin-section">
        <h3>Deleted Venues</h3>
        {deletedVenuesLoading ? (
          <p>Loading deleted venues…</p>
        ) : deletedVenuesError ? (
          <div className="error-message">{deletedVenuesError}</div>
        ) : deletedVenues.length === 0 ? (
          <p className="field-help">No deleted venues.</p>
        ) : (
          <table className="audit-log-table">
            <thead>
              <tr>
                <th>Venue</th>
                <th>Address</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {deletedVenues.map((venue) => (
                <tr key={venue.id}>
                  <td>{venue.name}</td>
                  <td>{venue.address}</td>
                  <td>
                    <button
                      className="btn-secondary"
                      onClick={() => handleUndeleteVenue(venue.id)}
                      disabled={!!undeletingVenue[venue.id]}
                    >
                      {undeletingVenue[venue.id] ? 'Restoring…' : 'Restore'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
};

export default Admin;
