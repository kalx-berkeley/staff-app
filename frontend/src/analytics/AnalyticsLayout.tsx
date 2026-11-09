import { useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import ImpersonationNotice from '../common/components/ImpersonationNotice';
import { useAuth } from '../common/contexts/authHooks';
import { HOME_TITLE, SUBSITES, subsiteForPath } from '../subsites';
import { ANALYTICS_TITLE } from './TabPage';
import { windowQuery } from './timeWindow';
import type { AnalyticsWindow } from './types';
import WindowPicker from './WindowPicker';

export interface LayoutContext {
  setResolvedWindow: (window: AnalyticsWindow) => void;
}

const TABS = [
  { to: '/', label: 'Overview', end: true },
  { to: '/venues', label: 'Venues' },
  { to: '/djs', label: 'DJs' },
  { to: '/reps', label: 'Promotions reps' },
  { to: '/short-links', label: 'Short links' },
  { to: '/usage', label: 'Site usage' },
];

// The analytics header: links to the other staff sites, the tabs and the
// shared time-window control. Tab links keep the chosen window.
export default function AnalyticsLayout() {
  const { user } = useAuth();
  const { search } = useLocation();
  const [resolved, setResolved] = useState<AnalyticsWindow | null>(null);
  const query = windowQuery(new URLSearchParams(search));
  const otherSubsites = SUBSITES.filter(
    (subsite) => subsite !== subsiteForPath('/analytics') && subsite.isAvailable(user),
  );

  return (
    <div className="analytics-page">
      <header>
        <nav className="directory-subsites" aria-label="Staff sites">
          <a href="/">{HOME_TITLE}</a>
          {otherSubsites.map((subsite) => (
            <a key={subsite.basePath} href={`${subsite.basePath}/`}>
              {subsite.name}
            </a>
          ))}
        </nav>
        <h1>{ANALYTICS_TITLE}</h1>
        <ImpersonationNotice />
        <nav className="analytics-tabs" aria-label="Analytics">
          {TABS.map((tab) => (
            <NavLink key={tab.to} to={`${tab.to}${query}`} end={tab.end}>
              {tab.label}
            </NavLink>
          ))}
        </nav>
        <WindowPicker resolved={resolved} />
      </header>
      <main>
        <Outlet context={{ setResolvedWindow: setResolved } satisfies LayoutContext} />
      </main>
    </div>
  );
}
