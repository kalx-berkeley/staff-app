import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { showsAPI } from '../api';
import PassGiveawayForm from './PassGiveawayForm';
import { DjNameInput, DJ_NAME_KEY, EnrichedShowName, FeatureBinBadge, KalxLiveBadge } from '../components';
import MarkdownContent from '../../common/components/MarkdownContent';
import { usePageTitle } from '../../common/hooks/usePageTitle';
import { useAuth } from '../../common/contexts/authHooks';
import type { ShowResponse, PassResponse } from '../types';
import type { APIError } from '../../common/types';
import WheelchairAccessibleChecks from './WheelchairAccessibleChecks';
import { canRecordDjGiveaways, formatShowRating, isMovieShow } from '../utils';
import { useGiveawayVisit } from '../tracking';

const DJ_NAME_INPUT_ID = 'dj-giveaway-name';

const GiveawayPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  // Away from the DJ studio, the page is view only: the form is disabled
  const isViewOnly = !canRecordDjGiveaways(user);
  const [show, setShow] = useState<ShowResponse | null>(null);
  usePageTitle(`Pass Giveaway${show ? `: ${show.event_name}` : ''} · DJ`);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [djName, setDjName] = useState(localStorage.getItem(DJ_NAME_KEY) || '');
  // KALX Staff Analytics counts each visit to this page and what came of it
  const visitId = useGiveawayVisit(id ? parseInt(id) : null, djName, !isViewOnly);

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

  const sortAvailablePasses = (passes: PassResponse[]): PassResponse[] => {
    const name = djName.trim().toLowerCase();
    return [...passes].sort((a, b) => {
      const aIsMe = !!name && a.preassigned_dj?.toLowerCase() === name;
      const bIsMe = !!name && b.preassigned_dj?.toLowerCase() === name;
      const aIsUnassigned = !a.preassigned_dj;
      const bIsUnassigned = !b.preassigned_dj;
      const aPriority = aIsMe ? 1 : aIsUnassigned ? 2 : 3;
      const bPriority = bIsMe ? 1 : bIsUnassigned ? 2 : 3;
      return aPriority - bPriority;
    });
  };

  if (loading) {
    return <div className="loading">Loading show details...</div>;
  }

  if (error) {
    return (
      <div className="error">
        <p>Error: {error}</p>
        <button onClick={loadShow} className="btn-primary">Retry</button>
        <button onClick={() => navigate(`/dj/shows/${id}`)} className="btn-secondary">
          Back to Show
        </button>
      </div>
    );
  }

  if (!show) {
    return <div className="error">Show not found</div>;
  }

  const passPairs = show.passes.filter((p) => p.pass_type === 'pair');
  const availablePasses = sortAvailablePasses(passPairs.filter((p) => p.status === 'available'));
  const firstAvailable = availablePasses[0] ?? null;
  const remainingPasses = availablePasses.slice(1);
  const remainingPreassigned = remainingPasses.filter((p) => p.preassigned_dj);
  const age = show.age_restriction;

  return (
    <div className="dj-show-document">
      {isViewOnly && (
        <div className="kalx-doc-instructions" role="note">
          <p>
            <strong>View only.</strong> Giveaways can only be recorded from the DJ studio,
            so Give Away and Tried are turned off here. This is how the page looks to the
            on-air DJ.
          </p>
        </div>
      )}

      <DjNameInput value={djName} onChange={setDjName} id={DJ_NAME_INPUT_ID} required />

      <div className="kalx-giveaway-split">
        <div className="kalx-giveaway-left">
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

              {show.caller_special_instructions && (
                <>
                  <span className="kalx-doc-label">Caller Special Instructions:</span>
                  <span className="kalx-doc-value"><MarkdownContent content={show.caller_special_instructions} /></span>
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
        </div>

        <div className="kalx-giveaway-right">
          <div className="kalx-doc-passes">
            <h3 className="kalx-passes-title">
              Pass Pairs &mdash; {show.available_pair_count} of {passPairs.length} available
            </h3>

            {passPairs.length === 0 && (
              <p className="no-passes">No pass pairs for this show.</p>
            )}

            {availablePasses.length === 0 && passPairs.length > 0 && (
              <p className="no-passes">All passes have been given away.</p>
            )}

            {firstAvailable && (
              <div className="kalx-pass-row">
                <div className="kalx-pass-meta">
                  {firstAvailable.preassigned_dj ? (
                    <span className="kalx-pass-preassign-dj">
                      Pre-assigned to: <strong>{firstAvailable.preassigned_dj}</strong>
                      {firstAvailable.preassigned_date && ` (${firstAvailable.preassigned_date})`}
                    </span>
                  ) : (
                    <span className="kalx-pass-available-badge">Available — ANY DJ</span>
                  )}
                </div>
                <PassGiveawayForm
                  pass={firstAvailable}
                  venueId={show.venue.id}
                  onSuccess={(outcome) =>
                    navigate(`/dj/shows/${id}`, {
                      state: outcome === 'tried' ? { justTried: true } : { justGaveAway: true },
                    })
                  }
                  djName={djName}
                  onMissingDjName={() => document.getElementById(DJ_NAME_INPUT_ID)?.focus()}
                  winFrequencyDays={show.venue.win_frequency_days}
                  winFrequencySharedWith={show.venue.win_frequency_shared_with}
                  requiresEmail={show.guest_list_requirements.requires_email_address}
                  viewOnly={isViewOnly}
                  visitId={visitId}
                />
              </div>
            )}

            {remainingPasses.length > 0 && (
              <div className="kalx-pass-remaining">
                <p>
                  {remainingPasses.length === 1
                    ? '1 more pass pair available after this one.'
                    : `${remainingPasses.length} more pass pairs available after this one.`}
                </p>
                {remainingPreassigned.length > 0 && (
                  <ul>
                    {remainingPreassigned.map((pass) => (
                      <li key={pass.id}>
                        Pre-assigned to <strong>{pass.preassigned_dj}</strong>
                        {pass.preassigned_date && ` (${pass.preassigned_date})`}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="kalx-doc-footer">
        <button onClick={() => navigate(`/dj/shows/${id}`)} className="btn-secondary">
          ← Back to Show
        </button>
      </div>
    </div>
  );
};

export default GiveawayPage;
