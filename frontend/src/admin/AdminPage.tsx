import ImpersonationNotice from '../common/components/ImpersonationNotice';
import { useAuth } from '../common/contexts/authHooks';
import { usePageTitle } from '../common/hooks/usePageTitle';
import { HOME_TITLE, SUBSITES, subsiteForPath } from '../subsites';
import AuditLogSection from './AuditLogSection';
import ImpersonationSection from './ImpersonationSection';
import JobsSection from './JobsSection';

export const ADMIN_TITLE = 'KALX Staff Admin';

// KALX Staff Admin: the admin tools that apply to every sub-site. Each
// sub-site's own admin tools stay in that sub-site (for example the pass
// giveaway's Promotions → Admin page).
export default function AdminPage() {
  usePageTitle(null, ADMIN_TITLE);
  const { user } = useAuth();
  const otherSubsites = SUBSITES.filter(
    (subsite) => subsite !== subsiteForPath('/admin') && subsite.isAvailable(user),
  );

  return (
    <div className="staff-admin-page">
      <header>
        <nav className="directory-subsites" aria-label="Staff sites">
          <a href="/">{HOME_TITLE}</a>
          {otherSubsites.map((subsite) => (
            <a key={subsite.basePath} href={`${subsite.basePath}/`}>
              {subsite.name}
            </a>
          ))}
        </nav>
        <h1>{ADMIN_TITLE}</h1>
        <ImpersonationNotice />
      </header>
      <main>
        <JobsSection />
        {user?.is_staging && <ImpersonationSection />}
        <AuditLogSection />
      </main>
    </div>
  );
}
