import { useState, useEffect } from 'react';
import { adminAPI, showsAPI, venuesAPI } from '../../services/api';
import type {
  JobStatus,
  JobRunResult,
  SeedResult,
  UserListItem,
  ImpersonateRequest,
  AuditLogItem,
  AutoCloseScheduleItem,
  LotteryScheduleItem,
  ShowResponse,
  VenueResponse,
  APIError,
} from '../../types';
import { useAuth } from '../../contexts/authHooks';
import { DatePicker } from '../shared';

const AUDIT_PAGE_SIZE = 50;

const toDateInputValue = (d: Date): string =>
  d.toLocaleDateString('en-CA', { timeZone: 'America/Los_Angeles' });

const defaultSince = (): string => {
  const d = new Date();
  d.setDate(d.getDate() - 30);
  return toDateInputValue(d);
};

const defaultUntil = (): string => toDateInputValue(new Date());

const formatRelativeTime = (isoString: string | null): string => {
  if (!isoString) return 'Never';
  const then = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - then.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
};

const formatFutureTime = (isoString: string | null): string => {
  if (!isoString) return 'Not scheduled';
  const then = new Date(isoString);
  const now = new Date();
  const diffMs = then.getTime() - now.getTime();
  if (diffMs <= 0) return 'Imminent';
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 60) return `in ${diffMins} minute${diffMins !== 1 ? 's' : ''}`;
  const diffHours = Math.floor(diffMins / 60);
  return `in ${diffHours} hour${diffHours !== 1 ? 's' : ''}`;
};

const Admin = () => {
  const { user } = useAuth();
  const isStaging = user?.is_staging ?? false;
  const isImpersonating =
    !!user?.impersonating_email ||
    user?.is_impersonating_dj_network ||
    user?.is_impersonating_station_office_network;

  const [jobStatuses, setJobStatuses] = useState<JobStatus[]>([]);
  const [jobRunning, setJobRunning] = useState<Record<string, boolean>>({});
  const [jobResult, setJobResult] = useState<Record<string, JobRunResult | null>>({});
  const [jobError, setJobError] = useState<Record<string, string | null>>({});

  const [seeding, setSeeding] = useState(false);
  const [seedResult, setSeedResult] = useState<SeedResult | null>(null);
  const [seedError, setSeedError] = useState<string | null>(null);
  const [seedAlreadyLoaded, setSeedAlreadyLoaded] = useState(false);

  const [userList, setUserList] = useState<UserListItem[]>([]);
  const [selectedUserEmail, setSelectedUserEmail] = useState('');
  const [impersonateError, setImpersonateError] = useState<string | null>(null);
  const [impersonateLoading, setImpersonateLoading] = useState(false);
  const [impersonateMode, setImpersonateMode] = useState<'user' | 'dj' | 'user_dj' | 'station_office'>('user');

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

  const [lotterySchedules, setLotterySchedules] = useState<LotteryScheduleItem[]>([]);
  const [lotterySchedulesLoading, setLotterySchedulesLoading] = useState(true);
  const [lotterySchedulesError, setLotterySchedulesError] = useState<string | null>(null);
  const [lotteryRunning, setLotteryRunning] = useState<Record<number, boolean>>({});
  const [lotteryRunResult, setLotteryRunResult] = useState<Record<number, string | null>>({});

  const [auditLog, setAuditLog] = useState<AuditLogItem[]>([]);
  const [auditLogLoading, setAuditLogLoading] = useState(false);
  const [auditLogError, setAuditLogError] = useState<string | null>(null);
  const [auditLogOffset, setAuditLogOffset] = useState(0);
  const [auditLogHasMore, setAuditLogHasMore] = useState(false);
  const [auditEventType, setAuditEventType] = useState('');
  const [auditActorEmail, setAuditActorEmail] = useState('');
  const [auditSince, setAuditSince] = useState(defaultSince);
  const [auditUntil, setAuditUntil] = useState(defaultUntil);
  const refreshJobStatuses = () => {
    adminAPI.getJobStatuses().then(setJobStatuses).catch(() => {});
  };

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
    refreshJobStatuses();
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
      adminAPI.listUsers().then(setUserList).catch(() => {});
      adminAPI.getSeedStatus().then((s) => setSeedAlreadyLoaded(s.seeded)).catch(() => {});
    }
  }, [isStaging]);

  const handleRunJob = async (jobId: string) => {
    setJobRunning((prev) => ({ ...prev, [jobId]: true }));
    setJobResult((prev) => ({ ...prev, [jobId]: null }));
    setJobError((prev) => ({ ...prev, [jobId]: null }));
    try {
      const result = await adminAPI.triggerJob(jobId);
      setJobResult((prev) => ({ ...prev, [jobId]: result }));
      refreshJobStatuses();
    } catch (err) {
      const apiError = err as APIError;
      setJobError((prev) => ({
        ...prev,
        [jobId]: typeof apiError.detail === 'string' ? apiError.detail : 'Job failed',
      }));
    } finally {
      setJobRunning((prev) => ({ ...prev, [jobId]: false }));
    }
  };

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

  const handleImpersonate = async (request: ImpersonateRequest) => {
    setImpersonateLoading(true);
    setImpersonateError(null);
    try {
      await adminAPI.startImpersonation(request);
      window.location.reload();
    } catch (err) {
      const apiError = err as APIError;
      setImpersonateError(
        typeof apiError.detail === 'string' ? apiError.detail : 'Failed to start impersonation'
      );
      setImpersonateLoading(false);
    }
  };

  const loadAuditLog = async (reset: boolean) => {
    setAuditLogLoading(true);
    setAuditLogError(null);
    const offset = reset ? 0 : auditLogOffset;
    try {
      const entries = await adminAPI.getAuditLog({
        event_type: auditEventType || undefined,
        actor_email: auditActorEmail || undefined,
        since: auditSince || undefined,
        until: auditUntil || undefined,
        limit: AUDIT_PAGE_SIZE,
        offset,
      });
      if (reset) {
        setAuditLog(entries);
        setAuditLogOffset(entries.length);
      } else {
        setAuditLog((prev) => [...prev, ...entries]);
        setAuditLogOffset((prev) => prev + entries.length);
      }
      setAuditLogHasMore(entries.length === AUDIT_PAGE_SIZE);
    } catch (err) {
      const apiError = err as APIError;
      setAuditLogError(
        typeof apiError.detail === 'string' ? apiError.detail : 'Failed to load audit log'
      );
    } finally {
      setAuditLogLoading(false);
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

  const handleEndImpersonation = async () => {
    setImpersonateLoading(true);
    setImpersonateError(null);
    try {
      await adminAPI.endImpersonation();
      window.location.reload();
    } catch (err) {
      const apiError = err as APIError;
      setImpersonateError(
        typeof apiError.detail === 'string' ? apiError.detail : 'Failed to end impersonation'
      );
      setImpersonateLoading(false);
    }
  };

  return (
    <div className="admin-container">
      <h2>Admin</h2>

      <section className="admin-section">
        <h3>Scheduled Jobs</h3>
        {jobStatuses.length === 0 ? (
          <p>Loading job statuses…</p>
        ) : (
          <table className="audit-log-table">
            <thead>
              <tr>
                <th>Job</th>
                <th>Last Run</th>
                <th>Next Run</th>
                <th>Action</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              {jobStatuses.map((job) => (
                <tr key={job.id}>
                  <td>{job.name}</td>
                  <td className="audit-log-time">{formatRelativeTime(job.last_run_at)}</td>
                  <td className="audit-log-time">{formatFutureTime(job.next_run_at)}</td>
                  <td>
                    <button
                      className="btn-primary btn-sm"
                      onClick={() => handleRunJob(job.id)}
                      disabled={!!jobRunning[job.id]}
                    >
                      {jobRunning[job.id] ? 'Running…' : 'Run Now'}
                    </button>
                  </td>
                  <td>
                    {jobError[job.id] && (
                      <span className="error-message">{jobError[job.id]}</span>
                    )}
                    {jobResult[job.id] && (
                      <span className={jobResult[job.id]!.success ? 'text-success' : 'error-message'}>
                        {jobResult[job.id]!.message}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="admin-section">
        <h3>Auto-close Schedules</h3>
        <p className="field-hint">
          Shows with auto-close enabled and their scheduled close times (Pacific Time).
        </p>
        {autoCloseLoading ? (
          <p>Loading…</p>
        ) : autoCloseError ? (
          <div className="error-message">{autoCloseError}</div>
        ) : autoCloseSchedules.length === 0 ? (
          <p className="field-hint">No auto-close schedules configured.</p>
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
                {autoCloseSchedules.map((item) => (
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
        )}
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
                        className="btn-primary btn-sm"
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
          <section className="admin-section">
            <h3>User Impersonation</h3>
            <p className="field-hint">
              Simulate different access contexts to test role-based behavior.
            </p>

            {isImpersonating && (
              <div className="impersonate-active">
                <p>
                  <strong>Currently impersonating:</strong>{' '}
                  {user?.impersonating_email ?? '(not logged in)'}
                  {user?.is_impersonating_dj_network && ' + DJ studio network'}
                  {user?.is_impersonating_station_office_network && ' + station office network'}
                </p>
                <button
                  className="btn-danger"
                  onClick={handleEndImpersonation}
                  disabled={impersonateLoading}
                >
                  End Impersonation
                </button>
              </div>
            )}

            {impersonateError && <div className="error-message">{impersonateError}</div>}

            <div className="impersonate-choices">
              <label className={`impersonate-choice${impersonateMode === 'user' ? ' impersonate-choice--selected' : ''}`}>
                <input
                  type="radio"
                  name="impersonateMode"
                  value="user"
                  checked={impersonateMode === 'user'}
                  onChange={() => setImpersonateMode('user')}
                  disabled={impersonateLoading}
                />
                <span className="impersonate-choice-title">Impersonate a user</span>
                <span className="impersonate-choice-desc">Logged in as a selected user, outside the DJ studio</span>
              </label>

              <label className={`impersonate-choice${impersonateMode === 'dj' ? ' impersonate-choice--selected' : ''}`}>
                <input
                  type="radio"
                  name="impersonateMode"
                  value="dj"
                  checked={impersonateMode === 'dj'}
                  onChange={() => setImpersonateMode('dj')}
                  disabled={impersonateLoading}
                />
                <span className="impersonate-choice-title">Impersonate DJ studio (not logged in)</span>
                <span className="impersonate-choice-desc">Request appears to come from the DJ studio network, but no user is logged in</span>
              </label>

              <label className={`impersonate-choice${impersonateMode === 'user_dj' ? ' impersonate-choice--selected' : ''}`}>
                <input
                  type="radio"
                  name="impersonateMode"
                  value="user_dj"
                  checked={impersonateMode === 'user_dj'}
                  onChange={() => setImpersonateMode('user_dj')}
                  disabled={impersonateLoading}
                />
                <span className="impersonate-choice-title">Impersonate a user in the DJ studio</span>
                <span className="impersonate-choice-desc">Logged in as a selected user and on the DJ studio network</span>
              </label>

              <label className={`impersonate-choice${impersonateMode === 'station_office' ? ' impersonate-choice--selected' : ''}`}>
                <input
                  type="radio"
                  name="impersonateMode"
                  value="station_office"
                  checked={impersonateMode === 'station_office'}
                  onChange={() => setImpersonateMode('station_office')}
                  disabled={impersonateLoading}
                />
                <span className="impersonate-choice-title">Impersonate station office (not logged in)</span>
                <span className="impersonate-choice-desc">Request appears to come from the station office network (not DJ studio), but no user is logged in</span>
              </label>
            </div>

            {(impersonateMode === 'user' || impersonateMode === 'user_dj') && userList.length > 0 && (
              <div className="impersonate-user-row">
                <select
                  value={selectedUserEmail}
                  onChange={(e) => setSelectedUserEmail(e.target.value)}
                  disabled={impersonateLoading}
                  className="impersonate-select"
                >
                  <option value="">— Select a user —</option>
                  {userList.map((u) => (
                    <option key={u.email} value={u.email}>
                      {u.name} ({u.role}) — {u.email}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="impersonate-action">
              <button
                className="btn-secondary"
                onClick={() => {
                  if (impersonateMode === 'dj') {
                    handleImpersonate({ email: null, is_dj_network: true });
                  } else if (impersonateMode === 'station_office') {
                    handleImpersonate({ email: null, is_dj_network: false, is_station_office_network: true });
                  } else if (impersonateMode === 'user' && selectedUserEmail) {
                    handleImpersonate({ email: selectedUserEmail, is_dj_network: false });
                  } else if (impersonateMode === 'user_dj' && selectedUserEmail) {
                    handleImpersonate({ email: selectedUserEmail, is_dj_network: true });
                  }
                }}
                disabled={
                  impersonateLoading ||
                  ((impersonateMode === 'user' || impersonateMode === 'user_dj') && !selectedUserEmail)
                }
              >
                {impersonateLoading ? 'Starting…' : 'Start Impersonation'}
              </button>
            </div>
          </section>

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

      <section className="admin-section">
        <h3>Audit Log</h3>
        <div className="audit-log-filters">
          <label className="audit-log-filter-label">
            From
            <DatePicker value={auditSince} onChange={setAuditSince} />
          </label>
          <label className="audit-log-filter-label">
            To
            <DatePicker value={auditUntil} onChange={setAuditUntil} />
          </label>
          <input
            type="text"
            placeholder="Event type"
            value={auditEventType}
            onChange={(e) => setAuditEventType(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && loadAuditLog(true)}
          />
          <input
            type="text"
            placeholder="Actor email"
            value={auditActorEmail}
            onChange={(e) => setAuditActorEmail(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && loadAuditLog(true)}
          />
          <button
            className="btn-primary"
            onClick={() => loadAuditLog(true)}
            disabled={auditLogLoading}
          >
            {auditLogLoading && auditLog.length === 0 ? 'Loading…' : 'Load'}
          </button>
        </div>
        {auditLogError && <div className="error-message">{auditLogError}</div>}
        {auditLog.length === 0 && !auditLogLoading && !auditLogError && (
          <p className="field-help">Use the filters above and click Load to fetch entries.</p>
        )}
        {auditLog.length > 0 && (
          <>
            <div className="audit-log-table-wrapper">
              <table className="audit-log-table">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Event</th>
                    <th>Actor</th>
                    <th>Role</th>
                    <th>Entity</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {auditLog.map((entry) => (
                    <tr key={entry.id}>
                      <td className="audit-log-time">
                        {new Date(entry.occurred_at).toLocaleString('en-US', { timeZone: 'America/Los_Angeles' })}
                      </td>
                      <td>
                        <code>{entry.event_type}</code>
                      </td>
                      <td>{entry.actor_email ?? '—'}</td>
                      <td>{entry.actor_role ?? '—'}</td>
                      <td>
                        {entry.entity_type
                          ? `${entry.entity_type}${entry.entity_id != null ? ` #${entry.entity_id}` : ''}`
                          : '—'}
                      </td>
                      <td className="audit-log-details">
                        {entry.details ? (
                          <details>
                            <summary>{JSON.stringify(entry.details)}</summary>
                            <pre>{JSON.stringify(entry.details, null, 2)}</pre>
                          </details>
                        ) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {auditLogHasMore && (
              <button
                className="btn-secondary"
                onClick={() => loadAuditLog(false)}
                disabled={auditLogLoading}
              >
                {auditLogLoading ? 'Loading…' : 'Load More'}
              </button>
            )}
          </>
        )}
      </section>
    </div>
  );
};

export default Admin;
