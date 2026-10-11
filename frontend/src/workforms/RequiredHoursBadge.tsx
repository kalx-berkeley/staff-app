import { formatHours, hoursShort, REQUIRED_MONTHLY_HOURS } from './utils';

// Whether a month's total reaches the required monthly hours, or how far short
// it is. The minimum doesn't apply in a month a leave of absence overlaps.
export default function RequiredHoursBadge({
  total,
  onLeave,
}: {
  total: number;
  onLeave: boolean;
}) {
  if (onLeave) {
    return (
      <span className="workforms-badge workforms-badge-pending">
        No {REQUIRED_MONTHLY_HOURS}-hour minimum during leave of absence
      </span>
    );
  }
  const short = hoursShort(total);
  if (short === 0) {
    return (
      <span className="workforms-badge workforms-badge-approved">
        ✓ {REQUIRED_MONTHLY_HOURS}-hour minimum met
      </span>
    );
  }
  return (
    <span className="workforms-badge workforms-badge-short">
      {formatHours(short)} h short of the {REQUIRED_MONTHLY_HOURS}-hour minimum
    </span>
  );
}
