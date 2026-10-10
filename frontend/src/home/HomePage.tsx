import { useAuth } from '../common/contexts/authHooks';
import { usePageTitle } from '../common/hooks/usePageTitle';
import { HOME_TITLE, SUBSITES } from '../subsites';
import UnauthorizedPage from '../common/components/UnauthorizedPage';

// The staff site's home page at /: a card for each sub-site the signed-in user
// can use. Links are plain anchors because each sub-site has its own router.
export default function HomePage() {
  usePageTitle(null, HOME_TITLE);
  const { user } = useAuth();

  if (user?.role === 'unauthorized') {
    return <UnauthorizedPage />;
  }

  const subsites = SUBSITES.filter((subsite) => subsite.isAvailable(user));

  return (
    <div className="home-page">
      <h1>{HOME_TITLE}</h1>
      <p className="home-subtitle">Internal tools for KALX staff and volunteers.</p>

      {subsites.length === 0 ? (
        <p className="home-empty">There are no staff tools available to your account.</p>
      ) : (
        <div className="home-cards">
          {subsites.map((subsite) => (
            <a key={subsite.basePath} className="home-card" href={`${subsite.basePath}/`}>
              <h2>{subsite.name}</h2>
              <p>{subsite.description}</p>
            </a>
          ))}
        </div>
      )}

      <footer className="home-footer">KALX 90.7 FM — UC Berkeley</footer>
    </div>
  );
}
