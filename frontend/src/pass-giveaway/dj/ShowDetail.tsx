import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { showsAPI } from '../api';
import { DjNameInput, DJ_NAME_KEY, EnrichedShowName, FeatureBinBadge, KalxLiveBadge } from '../components';
import MarkdownContent from '../../common/components/MarkdownContent';
import { formatPhone } from '../../common/utils';
import { usePageTitle } from '../../common/hooks/usePageTitle';
import { DJ_SHOW_GIVEAWAY_WINDOW_HOURS, canDjEditWinner, findRecentDjGiveaway, formatShowRating, isMovieShow } from '../utils';
import WinnerEditForm from './WinnerEditForm';
import WheelchairAccessibleChecks from './WheelchairAccessibleChecks';
import type { ShowResponse, PassResponse } from '../types';
import type { APIError } from '../../common/types';

const ShowDetail = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  // Set by GiveawayPage after a successful giveaway. The DJ has just used their
  // one pair for this show, so the "I'm off the mic" button would only
  // confuse them. Read once, then cleared
  // from history so a reload or a later visit shows the page as usual.
  // GiveawayPage sets justTried instead after Tried: nobody called in, so the
  // pass is still available and the off-the-mic button stays.
  const [{ justGaveAway, justTried }] = useState(() => {
    const state = location.state as { justGaveAway?: boolean; justTried?: boolean } | null;
    return { justGaveAway: state?.justGaveAway === true, justTried: state?.justTried === true };
  });
  useEffect(() => {
    if (justGaveAway || justTried) navigate(location.pathname, { replace: true, state: null });
    // Only on mount: clearing the state must not re-run when location changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [show, setShow] = useState<ShowResponse | null>(null);
  usePageTitle(`${show?.event_name ?? 'Show'} · DJ`);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [djName, setDjName] = useState(localStorage.getItem(DJ_NAME_KEY) || '');
  const [editingPassId, setEditingPassId] = useState<number | null>(null);
  // Whether the DJ clicked through the "pre-assigned to another DJ" warning.
  const [acknowledgedOthersPreassigned, setAcknowledgedOthersPreassigned] = useState(false);

  const loadShow = useCallback(async () => {
    if (!id) return;
    try {
      setLoading(true);
      setError(null);
      const data = await showsAPI.get(parseInt(id));
      setShow(data);
    } catch (err) {
      const apiError = err as APIError;
      setError(
        typeof apiError.detail === 'string' ? apiError.detail : 'Failed to load show'
      );
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadShow();
  }, [loadShow]);

  const formatDate = (dateStr: string) => {
    const [_y, _m, _d] = dateStr.split('-').map(Number); const date = new Date(_y, _m - 1, _d);
    return date.toLocaleDateString('en-US', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
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

  const formatDateTime = (dateTimeStr: string) => {
    const date = new Date(dateTimeStr);
    return date.toLocaleString('en-US', {
      timeZone: 'America/Los_Angeles',
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  };

  const sortAvailablePasses = (passes: PassResponse[]): PassResponse[] => {
    const name = djName.trim().toLowerCase();
    return [...passes].sort((a, b) => {
      const aIsMe = !!name && a.preassigned_dj?.toLowerCase() === name;
      const bIsMe = !!name && b.preassigned_dj?.toLowerCase() === name;
      const aIsUnassigned = !a.preassigned_dj;
      const bIsUnassigned = !b.preassigned_dj;
      // Priority order: my pre-assigned (1) > unassigned (2) > others' pre-assigned (3)
      const aPriority = aIsMe ? 1 : aIsUnassigned ? 2 : 3;
      const bPriority = bIsMe ? 1 : bIsUnassigned ? 2 : 3;
      return aPriority - bPriority;
    });
  };

  const handleWinnerSaved = (updated: PassResponse) => {
    setShow((prev) =>
      prev && {
        ...prev,
        passes: prev.passes.map((p) => (p.id === updated.id ? { ...p, ...updated } : p)),
      },
    );
    setEditingPassId(null);
  };

  if (loading) {
    return <div className="loading">Loading show details...</div>;
  }

  if (error) {
    return (
      <div className="error">
        <p>Error: {error}</p>
        <button onClick={loadShow} className="btn-primary">Retry</button>
        <button onClick={() => navigate('/dj/shows')} className="btn-secondary">
          Back to Shows
        </button>
      </div>
    );
  }

  if (!show) {
    return <div className="error">Show not found</div>;
  }

  const passPairs = show.passes.filter((p) => p.pass_type === 'pair');
  const availablePasses = sortAvailablePasses(passPairs.filter((p) => p.status === 'available'));
  const givenAwayPasses = passPairs.filter((p) => p.status === 'given_away');
  const hasPreviousActivity = givenAwayPasses.length > 0 || show.attempts.length > 0;
  // The show list only links here with "View" after a recent giveaway, and
  // the backend refuses a second pair for the show this DJ shift.
  const recentDjGiveaway = findRecentDjGiveaway(givenAwayPasses, djName);
  const canGiveAway = availablePasses.length > 0 && !justGaveAway && !recentDjGiveaway;
  // Every pair left is pre-assigned to another DJ, so giving one away on air
  // takes it from them. The DJ must click through a warning first.
  const normalizedDjName = djName.trim().toLowerCase();
  const othersPreassignedPasses = availablePasses.filter(
    (p) => p.preassigned_dj && p.preassigned_dj.trim().toLowerCase() !== normalizedDjName,
  );
  // One line per DJ and airdate, with how many pairs they hold.
  const othersPreassignedGroups = [
    ...othersPreassignedPasses
      .reduce((groups, p) => {
        const key = `${p.preassigned_dj}|${p.preassigned_date ?? ''}`;
        const group = groups.get(key) ?? { dj: p.preassigned_dj!, date: p.preassigned_date, count: 0 };
        group.count += 1;
        return groups.set(key, group);
      }, new Map<string, { dj: string; date: string | null; count: number }>())
      .values(),
  ];
  const onlyOthersPreassigned =
    canGiveAway && othersPreassignedPasses.length === availablePasses.length;
  const age = show.age_restriction;

  if (onlyOthersPreassigned && !acknowledgedOthersPreassigned) {
    return (
      <div className="dj-show-document">
        <DjNameInput value={djName} onChange={setDjName} id="dj-detail-name" />
        <div className="dj-preassigned-gate" role="alert">
          <h2>These passes are pre-assigned to another DJ</h2>
          <p>
            Every pass pair left for <strong>{show.event_name}</strong> is
            pre-assigned:
          </p>
          <ul>
            {othersPreassignedGroups.map((g) => (
              <li key={`${g.dj}|${g.date ?? ''}`}>
                {g.count > 1 && `${g.count} pairs: `}
                <strong>{g.dj}</strong>
                {g.date && ` for their show on ${formatDate(g.date)}`}
              </li>
            ))}
          </ul>
          <p>
            If you announce these passes on air, you'll be giving away a pair
            meant for another DJ. If that's not what you want, please pick a
            different show.
          </p>
          <div className="dj-preassigned-gate-actions">
            <button onClick={() => navigate('/dj/shows')} className="btn-primary">
              ← Pick a different show
            </button>
            <button
              onClick={() => setAcknowledgedOthersPreassigned(true)}
              className="btn-secondary"
            >
              I understand, show me this show
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="dj-show-document">
      <DjNameInput value={djName} onChange={setDjName} id="dj-detail-name" />

      <div className="kalx-doc-instructions">
        <p>
          Giveaways must be value neutral. Give only factual information about
          shows and don't offer any "opinions" on shows.
        </p>
        <p>
          Please mention these passes are courtesy of{' '}
          <strong>{show.venue.name}</strong>.
        </p>
      </div>

      <div className="kalx-doc-show-info">
        <h1 className="kalx-show-name">
          <EnrichedShowName eventName={show.event_name} bands={show.bands ?? []} />
          {show.co_announce && <span className="co-announce-badge" style={{ marginLeft: '0.75rem', fontSize: '0.65em', verticalAlign: 'middle' }}>📢 Co-Announce</span>}
          {show.in_feature_bin && (
            <span style={{ marginLeft: '0.75rem', fontSize: '0.65em', verticalAlign: 'middle' }}>
              <FeatureBinBadge releases={show.feature_bin_releases} />
            </span>
          )}
          {show.on_kalx_live && (
            <span style={{ marginLeft: '0.75rem', fontSize: '0.65em', verticalAlign: 'middle' }}>
              <KalxLiveBadge appearances={show.kalx_live_appearances} />
            </span>
          )}
        </h1>
        <p className="kalx-show-genre">{(show.genre ?? []).join(', ')}</p>
        <div className="kalx-doc-fields">
          <span className="kalx-doc-label">Venue:</span>
          <span className="kalx-doc-value kalx-value-large">
            {show.venue.has_logo && (
              <img
                src={`/api/venues/${show.venue.id}/logo`}
                alt={show.venue.show_name_with_logo ? '' : show.venue.name}
                className="venue-logo-display"
              />
            )}
            {(!show.venue.has_logo || show.venue.show_name_with_logo) && show.venue.name}
          </span>

          <span className="kalx-doc-label">Address:</span>
          <span className="kalx-doc-value">{show.venue.address}</span>

          <span className="kalx-doc-label">{show.show_start_date ? 'Dates:' : 'Date & Time:'}</span>
          <span className="kalx-doc-value kalx-value-large">
            {show.show_start_date
              ? formatDateRange(show.show_start_date, show.show_date)
              : `${formatDate(show.show_date)} at ${formatTime(show.show_time!)}`}
          </span>

          {show.on_air_description && (
            <>
              <span className="kalx-doc-label">On-Air Description:</span>
              <span className="kalx-doc-value"><MarkdownContent content={show.on_air_description} /></span>
            </>
          )}

          {isMovieShow(show) ? (
            <>
              <span className="kalx-doc-label">Movie Rating:</span>
              <span className="kalx-doc-value">{formatShowRating(show)}</span>
            </>
          ) : (
            <>
              <span className="kalx-doc-label">Age Restriction:</span>
              <span className="kalx-doc-value kalx-age-restriction">
                <span>21+ {age === '21+' ? '☑' : '☐'}</span>
                <span>18+ {age === '18+' ? '☑' : '☐'}</span>
                <span>All Ages {age === 'all_ages' ? '☑' : '☐'}</span>
              </span>
            </>
          )}

          <span className="kalx-doc-label">Wheelchair accessible?</span>
          <span className="kalx-doc-value">
            <WheelchairAccessibleChecks value={show.wheelchair_accessible} />
          </span>
        </div>
      </div>

      {justGaveAway && (
        <div className="success-message dj-giveaway-success" role="status">
          Pass pair given away
          {recentDjGiveaway?.recipient_name && <> to <strong>{recentDjGiveaway.recipient_name}</strong></>}. Thanks!
        </div>
      )}

      {justTried && (
        <div className="success-message dj-giveaway-success" role="status">
          Attempt recorded. No pass was given away, so it&apos;s still available. Thanks for trying!
        </div>
      )}

      {canGiveAway && (
        <div className="kalx-winner-cta">
          <p className="kalx-winner-cta-hint">
            After your mic-break, when you're ready to take calls from listeners,
            click the button below to record the winner.
          </p>
          <button
            className="btn-primary btn-winner-huge"
            onClick={() => navigate(`/dj/shows/${id}/giveaway`)}
          >
            I'm off the mic
          </button>
        </div>
      )}

      <div className="kalx-doc-passes">
        <h3 className="kalx-passes-title">
          Pass Pairs &mdash; {show.available_pair_count} of {passPairs.length} available
        </h3>

        {passPairs.length === 0 && (
          <p className="no-passes">No pass pairs for this show.</p>
        )}

        {hasPreviousActivity && (
          <div className="kalx-previous-winners">
            <h4 className="kalx-previous-winners-title">Previous Giveaway Activity</h4>
            {givenAwayPasses.map((pass) => (
              <div key={pass.id} className="kalx-pass-row">
                {editingPassId === pass.id ? (
                  <WinnerEditForm
                    pass={pass}
                    venueId={show.venue.id}
                    djName={djName}
                    requiresEmail={show.guest_list_requirements.requires_email_address}
                    onSaved={handleWinnerSaved}
                    onCancel={() => setEditingPassId(null)}
                  />
                ) : (
                  <div className="kalx-pass-given-info">
                    Winner: <strong>{pass.recipient_name}</strong>
                    {pass.recipient_phone && ` · ${formatPhone(pass.recipient_phone)}`}
                    {pass.given_away_by_dj && ` · DJ: ${pass.given_away_by_dj}`}
                    {pass.given_away_at && ` · ${formatDateTime(pass.given_away_at)}`}
                    {canDjEditWinner(pass, show, djName) && (
                      <button
                        type="button"
                        className="btn-small btn-secondary kalx-winner-edit-btn"
                        onClick={() => setEditingPassId(pass.id)}
                        title={`Fix a typo in the winner's details. You can edit them for ${DJ_SHOW_GIVEAWAY_WINDOW_HOURS} hours after the giveaway.`}
                      >
                        Edit
                      </button>
                    )}
                  </div>
                )}
              </div>
            ))}
            {show.attempts.map((attempt) => (
              <div key={attempt.id} className="kalx-pass-row">
                <div className="kalx-attempt-line">
                  No winner — attempted by <strong>{attempt.dj_name}</strong>
                  {` at ${formatDateTime(attempt.attempted_at)}`}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="kalx-doc-footer">
        <button onClick={() => navigate('/dj/shows')} className="btn-secondary">
          ← Back to Shows
        </button>
      </div>
    </div>
  );
};

export default ShowDetail;
