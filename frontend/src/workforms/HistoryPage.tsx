import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useAuth } from '../common/contexts/authHooks';
import { usePageTitle } from '../common/hooks/usePageTitle';
import { workformsAPI } from './api';
import DecisionBadge from './DecisionBadge';
import RequiredHoursBadge from './RequiredHoursBadge';
import type { MyWorkforms } from './types';
import { errorMessage, formatHours, formatMonth, statusLabel } from './utils';
import { WORKFORMS_TITLE } from './WorkformsLayout';

// Every month the staff member has a workform for, with each department's
// decision on the hours submitted. At /staff/:staffId, site admins see
// someone else's, read-only.
export default function HistoryPage() {
  const params = useParams();
  const staffId = params.staffId ? Number(params.staffId) : null;
  const readOnly = staffId !== null;
  const base = readOnly ? `/staff/${staffId}` : '';
  const [mine, setMine] = useState<MyWorkforms | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { user } = useAuth();
  usePageTitle(
    readOnly && mine?.staff_name ? `${mine.staff_name}’s workforms` : 'Past workforms',
    WORKFORMS_TITLE,
  );

  useEffect(() => {
    (staffId !== null ? workformsAPI.staffWorkforms(staffId) : workformsAPI.mine())
      .then(setMine)
      .catch((e) => setError(errorMessage(e)));
  }, [staffId]);

  if (error) return <div className="error-message">{error}</div>;
  if (!mine) return <p className="workforms-loading">Loading…</p>;

  const banner = readOnly && (
    <div className="info-message" role="note">
      Viewing {mine.staff_name ?? 'this staff member'}’s workforms. They’re read-only.
    </div>
  );
  const workforms = mine.workforms.filter((w) => w.status !== 'not_started');
  if (workforms.length === 0) {
    return (
      <>
        {banner}
        <p className="workforms-empty">
          {readOnly ? 'No workforms started yet.' : "You haven't started any workforms yet."}
        </p>
      </>
    );
  }

  return (
    <div className="workforms-history">
      {banner}
      {workforms.map((workform) => {
        const departments = Object.entries(workform.results);
        return (
          <section key={workform.month} className="workforms-card">
            <div className="workforms-card-heading">
              <h3>
                <Link to={`${base}/month/${workform.month}`}>{formatMonth(workform.month)}</Link>
              </h3>
              <span className="workforms-dept-total">{formatHours(workform.total_hours)} h</span>
              {(readOnly || !user?.is_department_head) && (
                <RequiredHoursBadge
                  total={workform.total_hours}
                  onLeave={workform.loa_overlaps_month}
                />
              )}
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
                {workform.is_open && !readOnly && (
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
