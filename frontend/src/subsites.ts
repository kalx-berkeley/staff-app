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
