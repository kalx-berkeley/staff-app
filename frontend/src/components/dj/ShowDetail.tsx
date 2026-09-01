import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { showsAPI } from '../../services/api';
import { DjNameInput, DJ_NAME_KEY, EnrichedShowName, MarkdownContent } from '../shared';
import { formatPhone } from '../../utils';
import type { ShowResponse, PassResponse, APIError } from '../../types';

const ShowDetail = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [show, setShow] = useState<ShowResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [djName, setDjName] = useState(localStorage.getItem(DJ_NAME_KEY) || '');

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
  const age = show.age_restriction;

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
        </h1>
        <p className="kalx-show-genre">{(show.genre ?? []).join(', ')}</p>
        <div className="kalx-doc-fields">
          <span className="kalx-doc-label">Venue:</span>
          <span className="kalx-doc-value kalx-value-large">
            {show.venue.has_logo ? (
              <img
                src={`/pass-giveaway/api/venues/${show.venue.id}/logo`}
                alt={show.venue.name}
                className="venue-logo-display"
              />
            ) : (
              show.venue.name
            )}
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

          <span className="kalx-doc-label">Age Restriction:</span>
          <span className="kalx-doc-value kalx-age-restriction">
            <span>21+ {age === '21+' ? '☑' : '☐'}</span>
            <span>18+ {age === '18+' ? '☑' : '☐'}</span>
            <span>All Ages {age === 'all_ages' ? '☑' : '☐'}</span>
          </span>

          <span className="kalx-doc-label">Wheelchair accessible?</span>
          <span className="kalx-doc-value">
            Yes {show.wheelchair_accessible ? '☑' : '☐'}
            {'   '}
            No {!show.wheelchair_accessible ? '☑' : '☐'}
          </span>
        </div>
      </div>

      {availablePasses.length > 0 && (
        <div className="kalx-winner-cta">
          <p className="kalx-winner-cta-hint">
            After your mic-break, when you're ready to take calls from listeners,
            click the button below to record the winner.
          </p>
          <button
            className="btn-primary btn-winner-huge"
            onClick={() => navigate(`/dj/shows/${id}/giveaway`)}
          >
            We've got a winner!
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
                <div className="kalx-pass-given-info">
                  Winner: <strong>{pass.recipient_name}</strong>
                  {pass.recipient_phone && ` · ${formatPhone(pass.recipient_phone)}`}
                  {pass.given_away_by_dj && ` · DJ: ${pass.given_away_by_dj}`}
                  {pass.given_away_at && ` · ${formatDateTime(pass.given_away_at)}`}
                </div>
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
