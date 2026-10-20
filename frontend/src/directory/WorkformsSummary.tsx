import type { WorkformMonth } from './types';
import { formatHours, formatMonthKey, workformMonthUrl } from './profileFormat';

const STATUS_LABELS: Record<WorkformMonth['status'], string> = {
  not_started: 'Not started',
  draft: 'Not submitted',
  submitted: 'Submitted',
  locked: 'Reviewed',
};

interface WorkformsSummaryProps {
  months: WorkformMonth[];
  // null on your own profile; the person's ID when a site admin views theirs
  otherStaffId: number | null;
}

// The last 12 months of someone's workforms, each linking to that month in
// KALX Workforms.
const WorkformsSummary = ({ months, otherStaffId }: WorkformsSummaryProps) => (
  <table className="profile-workforms">
    <thead>
      <tr>
        <th>Month</th>
        <th>Reported</th>
        <th>Approved</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
      {months.map((month) => (
        <tr key={month.month}>
          <td>
            <a href={workformMonthUrl(month.month, otherStaffId)}>{formatMonthKey(month.month)}</a>
          </td>
          <td>{formatHours(month.reported_hours)} h</td>
          <td>{formatHours(month.approved_hours)} h</td>
          <td>
            {STATUS_LABELS[month.status]}
            {month.is_late && <span className="profile-workforms-flag">Late</span>}
            {month.loa && <span className="profile-workforms-flag">LOA</span>}
          </td>
        </tr>
      ))}
    </tbody>
  </table>
);

export default WorkformsSummary;
