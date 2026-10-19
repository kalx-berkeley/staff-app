import type { DirectoryEntry } from './types';

const NEW_STATUS = '🆕';

/** Whether Airtable gives the staff member the "🆕" status (a new student, not yet Active). */
function isNewStaff(entry: DirectoryEntry): boolean {
  return entry.statuses.includes(NEW_STATUS);
}

/** A "🆕 New" badge for new students, or nothing for everyone else. */
export default function NewStaffBadge({ entry }: { entry: DirectoryEntry }) {
  if (!isNewStaff(entry)) return null;
  return (
    <>
      {' '}
      <span className="new-staff-badge" title="New student, not yet Active">
        🆕 New
      </span>
    </>
  );
}
