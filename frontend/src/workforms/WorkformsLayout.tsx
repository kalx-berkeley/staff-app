import type { ReactNode } from 'react';
import { NavLink } from 'react-router-dom';
import ImpersonationNotice from '../common/components/ImpersonationNotice';
import { useAuth } from '../common/contexts/authHooks';
import { HOME_TITLE, SUBSITES, subsiteForPath } from '../subsites';

export const WORKFORMS_TITLE = 'KALX Workforms';

// The header shared by every workforms page: links to the other staff sites,
// the title, and the sub-site's own navigation.
export default function WorkformsLayout({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const otherSubsites = SUBSITES.filter(
    (subsite) => subsite !== subsiteForPath('/workforms') && subsite.isAvailable(user)
  );
  const tab = ({ isActive }: { isActive: boolean }) =>
    isActive ? 'workforms-tab workforms-tab-active' : 'workforms-tab';

  return (
    <div className="workforms-page">
      <header className="workforms-header">
        <nav className="directory-subsites" aria-label="Staff sites">
          <a href="/">{HOME_TITLE}</a>
          {otherSubsites.map((subsite) => (
            <a key={subsite.basePath} href={`${subsite.basePath}/`}>
              {subsite.name}
            </a>
          ))}
        </nav>
        <h1>{WORKFORMS_TITLE}</h1>
        <div className="workforms-preview-notice" role="note">
          <strong>Under construction — this is not the official way to submit workforms.</strong>{' '}
          Workforms entered here don't count and don't replace the current process. Keep submitting
          your workforms the usual way.
        </div>
        <ImpersonationNotice />
        <nav className="workforms-tabs" aria-label="Workforms">
          <NavLink to="/" end className={tab}>
            {user?.is_department_head ? 'Staff view' : 'My workform'}
          </NavLink>
          <NavLink to="/history" className={tab}>
            Past workforms
          </NavLink>
          {user?.is_department_head && (
            <>
              <NavLink to="/review" className={tab}>
                Review
              </NavLink>
              <NavLink to="/people" className={tab}>
                People
              </NavLink>
              <NavLink to="/work-types" className={tab}>
                Work types
              </NavLink>
            </>
          )}
          <NavLink to="/settings" className={tab}>
            Settings
          </NavLink>
        </nav>
      </header>
      <main>{children}</main>
    </div>
  );
}
