import type { UserResponse } from './common/types';

/**
 * A sub-site of the KALX Staff App. Each one is served under its own top-level
 * path and has its own router (see App.tsx), so moving between sub-sites, or
 * to the home page at /, is a full page load rather than a client-side route.
 */
export interface Subsite {
  /** Top-level path the sub-site is served under; also its router basename. */
  basePath: string;
  name: string;
  /** One-line summary shown on the sub-site's home page card. */
  description: string;
  /** Whether the user may use the sub-site, which decides whether it's offered. */
  isAvailable: (user: UserResponse | null) => boolean;
}

export const SUBSITES: Subsite[] = [
  {
    basePath: '/pass-giveaway',
    name: 'Radio Pass Giveaway',
    description:
      'Manage concert pass giveaways — create shows, distribute passes, and record on-air winners.',
    isAvailable: (user) => !!user && user.role !== 'unauthorized',
  },
  {
    basePath: '/directory',
    name: 'KALX Staff Directory',
    description: 'Look up contact details for other KALX staff members.',
    // The promotions and staff roles both require Active status in Airtable,
    // which is what the directory API requires.
    isAvailable: (user) => user?.role === 'promotions' || user?.role === 'staff',
  },
  {
    basePath: '/workforms',
    name: 'KALX Workforms',
    description:
      'Under construction, not yet the official way to submit workforms. A preview of reporting your monthly work and having department heads review it.',
    // Active staff, as the workforms API requires, and only where the backend
    // has the sub-site turned on (staging, while it's under construction)
    isAvailable: (user) =>
      !!user?.workforms_enabled && (user.role === 'promotions' || user.role === 'staff'),
  },
  {
    basePath: '/admin',
    name: 'KALX Staff Admin',
    description:
      'Scheduled jobs, the audit log and, on staging, user impersonation, for every staff site.',
    // Site admins and promotions admins. Both flags describe the real user, so
    // an admin keeps them while impersonating someone who isn't one.
    isAvailable: (user) => !!user?.is_site_admin || !!user?.is_promotions_admin,
  },
];

export const HOME_TITLE = 'KALX Staff Portal';

/** The sub-site that `pathname` belongs to, or null for the home page. */
export function subsiteForPath(pathname: string): Subsite | null {
  return (
    SUBSITES.find(
      (subsite) =>
        pathname === subsite.basePath || pathname.startsWith(`${subsite.basePath}/`),
    ) ?? null
  );
}

/** Root URL of the sub-site the browser is in, or of the home page. */
export function currentSubsiteRoot(): string {
  const subsite = subsiteForPath(window.location.pathname);
  return subsite ? `${subsite.basePath}/` : '/';
}
