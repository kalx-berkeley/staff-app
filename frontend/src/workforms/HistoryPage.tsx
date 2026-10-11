import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { usePageTitle } from '../common/hooks/usePageTitle';
import { workformsAPI } from './api';
import DecisionBadge from './DecisionBadge';
import RequiredHoursBadge from './RequiredHoursBadge';
import type { MyWorkforms } from './types';
import { errorMessage, formatHours, formatMonth, statusLabel } from './utils';
import { WORKFORMS_TITLE } from './WorkformsLayout';

// Every month the staff member has a workform for, with each department's
// decision on the hours submitted.
export default function HistoryPage() {
  const [mine, setMine] = useState<MyWorkforms | null>(null);
  const [error, setError] = useState<string | null>(null);
  usePageTitle('Past workforms', WORKFORMS_TITLE);

  useEffect(() => {
    workformsAPI
      .mine()
      .then(setMine)
      .catch((e) => setError(errorMessage(e)));
  }, []);

  if (error) return <div className="error-message">{error}</div>;
  if (!mine) return <p className="workforms-loading">Loading…</p>;

  const workforms = mine.workforms.filter((w) => w.status !== 'not_started');
  if (workforms.length === 0) {
    return <p className="workforms-empty">You haven't started any workforms yet.</p>;
  }

  return (
    <div className="workforms-history">
      {workforms.map((workform) => {
        const departments = Object.entries(workform.results);
        return (
          <section key={workform.month} className="workforms-card">
            <div className="workforms-card-heading">
              <h3>
                <Link to={`/month/${workform.month}`}>{formatMonth(workform.month)}</Link>
              </h3>
              <span className="workforms-dept-total">{formatHours(workform.total_hours)} h</span>
              <RequiredHoursBadge
                total={workform.total_hours}
                onLeave={workform.loa_overlaps_month}
              />
              <span className="workforms-status">{statusLabel(workform)}</span>
              {workform.is_late && <span className="leave-badge">Late</span>}
            </div>
            {departments.length > 0 && (
              <table className="workforms-results">
                <tbody>
                  {departments.map(([department, result]) => (
                    <tr key={department}>
                      <th scope="row">{department}</th>
                      <td>{formatHours(result.hours ?? 0)} h</td>
                      <td>
                        <DecisionBadge decision={result.decision} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {workform.status === 'draft' && (
              <p className="workforms-hint">
                Not submitted yet.{' '}
                {workform.is_open && (
                  <Link to={`/month/${workform.month}`}>Finish and submit it</Link>
                )}
              </p>
            )}
            {workform.status !== 'draft' && departments.length === 0 && (
              <p className="workforms-hint">Submitted with no hours.</p>
            )}
          </section>
        );
      })}
    </div>
  );
}
