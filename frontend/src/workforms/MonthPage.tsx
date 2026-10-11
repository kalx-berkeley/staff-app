import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { usePageTitle } from '../common/hooks/usePageTitle';
import { formatLeave } from '../common/utils';
import { workformsAPI } from './api';
import DecisionBadge from './DecisionBadge';
import EntryForm from './EntryForm';
import type { Departments, Entry, EntryInput, Workform, WorkformSummary } from './types';
import {
  errorMessage,
  formatDay,
  formatHours,
  formatMonth,
  groupEntries,
  statusLabel,
  totalHours,
} from './utils';
import { WORKFORMS_TITLE } from './WorkformsLayout';

function formatDeadline(value: string): string {
  return new Date(value).toLocaleString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    timeZone: 'America/Los_Angeles',
  });
}

function LoaNote({ entry }: { entry: Pick<Entry, 'loa_flag'> }) {
  if (entry.loa_flag === 'inside') {
    return <span className="leave-badge">During your leave of absence</span>;
  }
  if (entry.loa_flag === 'may_overlap') {
    return <span className="workforms-loa-soft">May overlap your leave of absence</span>;
  }
  return null;
}

// One month's workform: add entries through the month, then submit it. A
// submitted workform can still be changed and resubmitted until a
// department head has reviewed it.
export default function MonthPage() {
  const params = useParams();
  const [month, setMonth] = useState<string | null>(params.month ?? null);
  const [openMonths, setOpenMonths] = useState<WorkformSummary[]>([]);
  const [workform, setWorkform] = useState<Workform | null>(null);
  const [departments, setDepartments] = useState<Departments | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  usePageTitle(month ? formatMonth(month) : null, WORKFORMS_TITLE);

  useEffect(() => {
    workformsAPI
      .mine()
      .then((mine) => {
        setOpenMonths(mine.workforms.filter((w) => mine.open_months.includes(w.month)));
        setMonth(params.month ?? mine.open_months[0]);
      })
      .catch((e) => setError(errorMessage(e)));
    // Statuses change as the workform is edited and submitted
  }, [params.month, workform?.status]);

  const load = useCallback(async () => {
    if (!month) return;
    try {
      const [loaded, depts] = await Promise.all([
        workformsAPI.get(month),
        departments ? Promise.resolve(departments) : workformsAPI.departments(),
      ]);
      setWorkform(loaded);
      setDepartments(depts);
      setError(null);
    } catch (e) {
      setError(errorMessage(e));
    }
  }, [month, departments]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [month]);

  if (error && !workform) return <div className="error-message">{error}</div>;
  if (!workform || !departments || !month) return <p className="workforms-loading">Loading…</p>;

  const editable = workform.is_open && workform.status !== 'locked';
  const groups = groupEntries(workform.entries);
  const monthTotal = totalHours(workform.entries);
  const isSubmitted = workform.status === 'submitted' || workform.status === 'locked';
  const loaEntries = workform.entries.filter((e) => e.loa_flag);
  const hasLeave = !!(workform.loa_start || workform.loa_end);

  const run = async (action: () => Promise<unknown>) => {
    setNotice(null);
    await action();
    await load();
  };

  const add = (entry: EntryInput) =>
    run(() => workformsAPI.addEntry(month, entry)).catch((e) => {
      throw new Error(errorMessage(e));
    });

  const update = (id: number) => (entry: EntryInput) =>
    run(async () => {
      await workformsAPI.updateEntry(month, id, entry);
      setEditingId(null);
    }).catch((e) => {
      throw new Error(errorMessage(e));
    });

  const remove = async (entry: Entry) => {
    if (
      !window.confirm(`Delete this ${formatHours(entry.hours)}-hour ${entry.department} entry?`)
    ) {
      return;
    }
    try {
      await run(() => workformsAPI.deleteEntry(month, entry.id));
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  const submit = async () => {
    setSubmitting(true);
    try {
      await workformsAPI.submit(month);
      setConfirming(false);
      setError(null);
      await load();
      setNotice(
        isSubmitted ? 'Your changes have been submitted.' : 'Your workform has been submitted.'
      );
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="workforms-month">
      {openMonths.length > 1 && (
        <nav className="workforms-month-switch" aria-label="Open workforms">
          {openMonths.map((open) => (
            <Link
              key={open.month}
              to={`/month/${open.month}`}
              className={open.month === month ? 'workforms-month-link-active' : undefined}
              aria-current={open.month === month ? 'page' : undefined}
            >
              {formatMonth(open.month)}
              <span className="workforms-month-status">{statusLabel(open)}</span>
            </Link>
          ))}
        </nav>
      )}

      <div className="workforms-month-heading">
        <h2>{formatMonth(month)}</h2>
        <span className="workforms-month-total">
          {formatHours(monthTotal)} {monthTotal === 1 ? 'hour' : 'hours'}
        </span>
      </div>

      {notice && (
        <div className="success-message" role="status">
          {notice}
        </div>
      )}
      {error && (
        <div className="error-message" role="alert">
          {error}
        </div>
      )}

      {workform.status === 'locked' && (
        <div className="info-message">
          A department head has reviewed this workform, so it can't be changed. Talk to the
          department head if something needs correcting.
        </div>
      )}
      {workform.status === 'submitted' && !workform.has_unsent_changes && (
        <div className="info-message">
          Submitted. You can still change it and resubmit until a department head reviews it.
        </div>
      )}
      {workform.has_unsent_changes && editable && (
        <div className="workforms-warning">
          You've changed this workform since you submitted it. Resubmit it so the department heads
          see your changes.
        </div>
      )}
      {!workform.is_open && workform.status !== 'locked' && (
        <div className="info-message">This month's workform is closed.</div>
      )}
      {editable && !isSubmitted && (
        <p className="workforms-deadline">
          {workform.would_be_late ? (
            <span className="workforms-warning-text">
              The deadline for this workform was {formatDeadline(workform.deadline)}. You can still
              submit it, but late hours might not count.
            </span>
          ) : (
            <>Due by the end of {formatDeadline(workform.deadline)}.</>
          )}
        </p>
      )}
      {workform.is_late && <p className="workforms-warning-text">Submitted after the deadline.</p>}
      {hasLeave && loaEntries.length > 0 && (
        <div className="workforms-warning">
          You're on leave of absence {formatLeave(workform)}. Hours marked below may have been
          during your leave.
        </div>
      )}

      {editable && (
        <section className="workforms-card" aria-labelledby="add-work">
          <h3 id="add-work">Add work</h3>
          <p className="workforms-hint">
            Add each piece of work as you go, or add one entry for everything you did in a
            department this month. Entries in the same department are combined when you submit.
          </p>
          <EntryForm month={month} departments={departments} submitLabel="Add" onSave={add} />
        </section>
      )}

      {groups.size === 0 && (
        <p className="workforms-empty">
          {editable
            ? 'No work added yet. If you did no work this month, you can submit a workform with no hours.'
            : 'No hours on this workform.'}
        </p>
      )}

      {[...groups.entries()].map(([department, entries]) => {
        const result = workform.results[department];
        return (
          <section key={department} className="workforms-card">
            <div className="workforms-card-heading">
              <h3>{department}</h3>
              <span className="workforms-dept-total">{formatHours(totalHours(entries))} h</span>
              {isSubmitted && result && <DecisionBadge decision={result.decision} />}
            </div>
            <ul className="workforms-entries">
              {entries.map((entry) =>
                editingId === entry.id ? (
                  <li key={entry.id}>
                    <EntryForm
                      month={month}
                      departments={departments}
                      initial={entry}
                      submitLabel="Save"
                      onSave={update(entry.id)}
                      onCancel={() => setEditingId(null)}
                    />
                  </li>
                ) : (
                  <li key={entry.id} className="workforms-entry">
                    <span className="workforms-entry-date">
                      {entry.work_date ? formatDay(entry.work_date) : 'No date'}
                    </span>
                    <span className="workforms-entry-hours">{formatHours(entry.hours)} h</span>
                    <span className="workforms-entry-text">
                      {entry.description} <LoaNote entry={entry} />
                    </span>
                    {editable && (
                      <span className="workforms-entry-buttons">
                        <button
                          type="button"
                          className="btn-secondary btn-small"
                          onClick={() => setEditingId(entry.id)}
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          className="btn-danger btn-small"
                          onClick={() => remove(entry)}
                        >
                          Delete
                        </button>
                      </span>
                    )}
                  </li>
                )
              )}
            </ul>
          </section>
        );
      })}

      {/* Departments whose Airtable values aren't backed by entries here
          (for example a record made by hand) */}
      {Object.entries(workform.results)
        .filter(([department]) => !groups.has(department))
        .map(([department, result]) => (
          <section key={department} className="workforms-card">
            <div className="workforms-card-heading">
              <h3>{department}</h3>
              <span className="workforms-dept-total">{formatHours(result.hours ?? 0)} h</span>
              <DecisionBadge decision={result.decision} />
            </div>
            {result.description && <p className="workforms-airtable-text">{result.description}</p>}
          </section>
        ))}

      {editable && (!isSubmitted || workform.has_unsent_changes) && (
        <div className="workforms-submit">
          {!confirming ? (
            <button type="button" className="btn-primary" onClick={() => setConfirming(true)}>
              {isSubmitted ? 'Resubmit workform' : 'Submit workform'}
            </button>
          ) : (
            <div className="workforms-confirm" role="dialog" aria-label="Confirm submission">
              <p>
                Submit {formatHours(monthTotal)} {monthTotal === 1 ? 'hour' : 'hours'} for{' '}
                {formatMonth(month)}
                {groups.size > 0 && ` in ${[...groups.keys()].join(', ')}`}?
              </p>
              {groups.size === 0 && <p>This is a workform with no hours.</p>}
              {workform.would_be_late && (
                <p className="workforms-warning-text">
                  This is after the deadline, so these hours might not count.
                </p>
              )}
              {loaEntries.length > 0 && (
                <p className="workforms-warning-text">
                  {loaEntries.length === 1 ? 'One entry' : `${loaEntries.length} entries`} may be
                  during your leave of absence. Department heads will see this.
                </p>
              )}
              <div className="workforms-entry-actions">
                <button
                  type="button"
                  className="btn-primary"
                  onClick={submit}
                  disabled={submitting}
                >
                  {submitting ? 'Submitting…' : 'Submit'}
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setConfirming(false)}
                  disabled={submitting}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {!params.month || workform.is_open ? null : (
        <p>
          <Link to="/history">Back to past workforms</Link>
        </p>
      )}
    </div>
  );
}
