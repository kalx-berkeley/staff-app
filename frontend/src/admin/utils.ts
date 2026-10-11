// Time formatting helpers for KALX Staff Admin.

/** "5 minutes ago", "3 days ago", or "Never" for null. */
export const formatRelativeTime = (isoString: string | null, now = new Date()): string => {
  if (!isoString) return 'Never';
  const diffMs = now.getTime() - new Date(isoString).getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
};

/** "in 5 minutes", "in 3 hours", or "Not scheduled" for null. */
export const formatFutureTime = (isoString: string | null, now = new Date()): string => {
  if (!isoString) return 'Not scheduled';
  const diffMs = new Date(isoString).getTime() - now.getTime();
  if (diffMs <= 0) return 'Imminent';
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 60) return `in ${diffMins} minute${diffMins !== 1 ? 's' : ''}`;
  const diffHours = Math.floor(diffMins / 60);
  return `in ${diffHours} hour${diffHours !== 1 ? 's' : ''}`;
};

/** A date as YYYY-MM-DD in Pacific time, for date inputs. */
export const toPacificDateInputValue = (d: Date): string =>
  d.toLocaleDateString('en-CA', { timeZone: 'America/Los_Angeles' });
