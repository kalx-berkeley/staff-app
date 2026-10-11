import type { Decision } from './types';

// A department's decision on submitted hours: Approved, Denied, or pending.
export default function DecisionBadge({ decision }: { decision: Decision | null }) {
  if (decision === 'Approved') {
    return <span className="workforms-badge workforms-badge-approved">Approved</span>;
  }
  if (decision === 'Denied') {
    return <span className="workforms-badge workforms-badge-denied">Denied</span>;
  }
  return <span className="workforms-badge workforms-badge-pending">Pending review</span>;
}
