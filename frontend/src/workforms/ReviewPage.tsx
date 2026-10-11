import { useCallback, useEffect, useState } from 'react';
import { Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { usePageTitle } from '../common/hooks/usePageTitle';
import { formatLeave } from '../common/utils';
import { reviewAPI } from './api';
import DecisionBadge from './DecisionBadge';
import type { Decision, ReviewItem, ReviewOverview, ReviewQueue } from './types';
import { errorMessage, formatDay, formatHours, formatMonth, nextPendingIndex } from './utils';
import { WORKFORMS_TITLE } from './WorkformsLayout';

// The API's timestamps are UTC, without a zone when they come from the database.
function formatSubmitted(value: string): string {
  const utc = /(Z|[+-]\d\d:\d\d)$/.test(value) ? value : `${value}Z`;
  return new Date(utc).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZone: 'America/Los_Angeles',
  });
}

function ReviewDetail({
  item,
  onDecide,
  deciding,
}: {
  item: ReviewItem;
  onDecide: (decision: Decision | null) => void;
  deciding: boolean;
}) {
  return (
    <article className="workforms-review-detail" aria-label={`${item.staff_name}'s hours`}>
      <div className="workforms-card-heading">
        <h3>{item.staff_name}</h3>
        <DecisionBadge decision={item.decision} />
      </div>
      <p className="workforms-review-total">
        <strong>{formatHours(item.hours ?? 0)}</strong> {item.hours === 1 ? 'hour' : 'hours'}
      </p>
      <p className="workforms-hint">
        {item.submitted_at && <>Submitted {formatSubmitted(item.submitted_at)}. </>}
        {item.is_late && <span className="leave-badge">Late</span>}
      </p>
      {item.loa_overlaps_month && (
        <div className="workforms-warning">
          {item.staff_name} was on leave of absence {formatLeave(item)} when they submitted this.
          Check the entries marked below.
        </div>
      )}
      {item.edited_in_airtable && (
        <div className="info-message">
          These hours were changed in Airtable after they were submitted
          {item.entries.length > 0 ? ', so they may not match the entries below.' : '.'}
          {item.description && <p className="workforms-airtable-text">{item.description}</p>}
        </div>
      )}
      {item.entries.length > 0 && (
        <ul className="workforms-entries">
          {item.entries.map((entry, i) => (
            <li key={i} className="workforms-entry">
              <span className="workforms-entry-date">
                {entry.work_date ? formatDay(entry.work_date) : 'No date'}
              </span>
              <span className="workforms-entry-hours">{formatHours(entry.hours)} h</span>
              <span className="workforms-entry-text">
                {entry.description}{' '}
                {entry.loa_flag === 'inside' && (
                  <span className="leave-badge">During leave of absence</span>
                )}
                {entry.loa_flag === 'may_overlap' && (
                  <span className="workforms-loa-soft">May overlap leave of absence</span>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
      <div className="workforms-entry-actions">
        <button
          type="button"
          className="btn-primary workforms-approve"
          disabled={deciding || item.decision === 'Approved'}
          onClick={() => onDecide('Approved')}
        >
          Approve
        </button>
        <button
          type="button"
          className="btn-danger"
          disabled={deciding || item.decision === 'Denied'}
          onClick={() => onDecide('Denied')}
        >
          Deny
        </button>
        {item.decision && (
          <button
            type="button"
            className="btn-secondary"
            disabled={deciding}
            onClick={() => onDecide(null)}
          >
            Clear decision
          </button>
        )}
      </div>
    </article>
  );
}

// Department heads review a month's submissions for one department at a
// time: a list of people on one side, one person's hours on the other, and
// a decision moves on to the next person still waiting.
export default function ReviewPage() {
  const params = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [overview, setOverview] = useState<ReviewOverview | null>(null);
  const [pending, setPending] = useState<Record<string, number>>({});
  const [queue, setQueue] = useState<ReviewQueue | null>(null);
  const [selected, setSelected] = useState(0);
  const [deciding, setDeciding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  usePageTitle('Review', WORKFORMS_TITLE);

  const month = params.month;
  const allDepartments = overview
    ? [...overview.own_departments, ...overview.fallback_departments]
    : [];
  const department = searchParams.get('department') ?? overview?.default_department ?? null;

  useEffect(() => {
    reviewAPI
      .overview()
      .then(setOverview)
      .catch((e) => setError(errorMessage(e)));
  }, []);

  useEffect(() => {
    if (!month) return;
    reviewAPI
      .pending(month)
      .then((counts) => setPending(counts.pending))
      .catch((e) => setError(errorMessage(e)));
  }, [month, queue]);

  const loadQueue = useCallback(async () => {
    if (!month || !department || !allDepartments.includes(department)) return;
    try {
      const loaded = await reviewAPI.queue(month, department);
      setQueue(loaded);
      const first = loaded.items.findIndex((i) => !i.decision);
      setSelected(first >= 0 ? first : 0);
      setError(null);
    } catch (e) {
      setError(errorMessage(e));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [month, department, overview]);

  useEffect(() => {
    setQueue(null);
    loadQueue();
  }, [loadQueue]);

  if (error && !overview) return <div className="error-message">{error}</div>;
  if (!overview) return <p className="workforms-loading">Loading…</p>;
  if (!month) return <Navigate to={`/review/${overview.default_month}`} replace />;

  const decide = async (decision: Decision | null) => {
    if (!queue || !department) return;
    const item = queue.items[selected];
    setDeciding(true);
    try {
      const updated = await reviewAPI.decide(item.airtable_record_id, department, decision);
      const items = queue.items.map((i, index) => (index === selected ? updated : i));
      const reviewed = items.filter((i) => i.decision).length;
      setQueue({ ...queue, items, reviewed, remaining: items.length - reviewed });
      setError(null);
      if (decision) {
        const next = nextPendingIndex(items, selected);
        if (next !== null) setSelected(next);
      }
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setDeciding(false);
    }
  };

  const percent = queue && queue.total ? Math.round((queue.reviewed / queue.total) * 100) : 0;
  const optionLabel = (d: string) => (pending[d] ? `${d} (${pending[d]} waiting)` : d);

  return (
    <div className="workforms-review">
      <div className="workforms-review-toolbar">
        <label>
          Month
          <select value={month} onChange={(e) => navigate(`/review/${e.target.value}`)}>
            {(overview.months.includes(month) ? overview.months : [month, ...overview.months]).map(
              (m) => (
                <option key={m} value={m}>
                  {formatMonth(m)}
                </option>
              )
            )}
          </select>
        </label>
        <label>
          Department
          <select
            value={department ?? ''}
            onChange={(e) => setSearchParams({ department: e.target.value })}
          >
            <optgroup label="Your departments">
              {overview.own_departments.map((d) => (
                <option key={d} value={d}>
                  {optionLabel(d)}
                </option>
              ))}
            </optgroup>
            {overview.fallback_departments.length > 0 && (
              <optgroup label="Other departments (as Operations)">
                {overview.fallback_departments.map((d) => (
                  <option key={d} value={d}>
                    {optionLabel(d)}
                  </option>
                ))}
              </optgroup>
            )}
          </select>
        </label>
      </div>

      {error && (
        <div className="error-message" role="alert">
          {error}
        </div>
      )}

      {!queue ? (
        <p className="workforms-loading">Loading…</p>
      ) : queue.total === 0 ? (
        <p className="workforms-empty">
          No one has submitted {department} hours for {formatMonth(month)}.
        </p>
      ) : (
        <>
          <div className="workforms-progress" role="status">
            <div className="workforms-progress-bar" aria-hidden="true">
              <div style={{ width: `${percent}%` }} />
            </div>
            <span>
              {queue.reviewed} of {queue.total} reviewed, {queue.remaining} remaining
            </span>
          </div>
          <div className="workforms-review-panes">
            <ul className="workforms-review-list" aria-label="Submissions">
              {queue.items.map((item, index) => (
                <li key={item.airtable_record_id}>
                  <button
                    type="button"
                    className={
                      index === selected
                        ? 'workforms-review-person workforms-review-person-active'
                        : 'workforms-review-person'
                    }
                    aria-current={index === selected ? 'true' : undefined}
                    onClick={() => setSelected(index)}
                  >
                    <span className="workforms-review-name">{item.staff_name}</span>
                    <span className="workforms-review-hours">{formatHours(item.hours ?? 0)} h</span>
                    <span className="workforms-review-badges">
                      {item.is_late && <span className="leave-badge">Late</span>}
                      {item.loa_overlaps_month && <span className="leave-badge">LOA</span>}
                      <DecisionBadge decision={item.decision} />
                    </span>
                  </button>
                </li>
              ))}
            </ul>
            {queue.items[selected] && (
              <ReviewDetail item={queue.items[selected]} onDecide={decide} deciding={deciding} />
            )}
          </div>
        </>
      )}
    </div>
  );
}
