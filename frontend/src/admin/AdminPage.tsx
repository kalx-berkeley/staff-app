import ImpersonationNotice from '../common/components/ImpersonationNotice';
import { useAuth } from '../common/contexts/authHooks';
import { usePageTitle } from '../common/hooks/usePageTitle';
import { HOME_TITLE, SUBSITES, subsiteForPath } from '../subsites';
import AuditLogSection from './AuditLogSection';
import DjQuizDeadlinesSection from './DjQuizDeadlinesSection';
import ImpersonationSection from './ImpersonationSection';
import JobsSection from './JobsSection';
import ShortLinksSection from './ShortLinksSection';

export const ADMIN_TITLE = 'KALX Staff Admin';

// KALX Staff Admin: the admin tools that apply to every sub-site. Each
// sub-site's own admin tools stay in that sub-site (for example the pass
// giveaway's Promotions → Admin page), plus the /go/ short links. Site admins
// can use all of it; promotions admins can see the jobs without running them,
// and the pass giveaway's audit log entries.
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
        {user?.is_staging && user.is_site_admin && <ImpersonationSection />}
        {user?.is_site_admin && <ShortLinksSection />}
        {user?.directory_enabled && user.is_site_admin && <DjQuizDeadlinesSection />}
        <AuditLogSection />
      </main>
    </div>
  );
}
