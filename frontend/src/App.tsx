import { useState, type ComponentType } from 'react';
import { AUTH_DIAG_KEY } from './common/api';
import LoadingScreen from './common/components/LoadingScreen';
import StagingBanner from './common/components/StagingBanner';
import { useAuth } from './common/contexts/authHooks';
import { isStagingEnvironment } from './common/utils';
import DirectoryApp from './directory/DirectoryApp';
import HomeApp from './home/HomeApp';
import PassGiveawayApp from './pass-giveaway/PassGiveawayApp';
import { subsiteForPath } from './subsites';

// The app shell: waits for the signed-in user, then hands the page to the
// sub-site the URL is in (see SUBSITES in subsites.ts), or to the home page.

// Diagnostic banner: rendered when a 401 redirect loop has been detected.
// Shows which API endpoint triggered the redirect and stops the loop from
// continuing by letting errors propagate instead of redirecting again.
function AuthDiagBanner() {
  const [diag, setDiag] = useState<{
    url: string;
    method: string;
    body: unknown;
    fromPath: string;
    at: string;
  } | null>(() => {
    try {
      const raw = sessionStorage.getItem(AUTH_DIAG_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });

  if (!diag) return null;

  return (
    <div style={{
      position: 'fixed', top: isStagingEnvironment() ? '2rem' : 0, left: 0, right: 0, zIndex: 9999,
      background: '#b71c1c', color: '#fff', padding: '0.6rem 1rem',
      fontFamily: 'monospace', fontSize: '0.8rem', lineHeight: 1.6,
      display: 'flex', alignItems: 'baseline', gap: '0.5rem', flexWrap: 'wrap',
    }}>
      <strong>Auth loop diagnostic</strong>
      <span>— 401 from <strong>{diag.method} {diag.url}</strong></span>
      <span>(at path <code style={{ background: 'rgba(0,0,0,0.25)', padding: '0 0.25rem' }}>{diag.fromPath}</code>,
        {' '}{diag.at})</span>
      {diag.body !== undefined && (
        <span>· response body: <code style={{ background: 'rgba(0,0,0,0.25)', padding: '0 0.25rem' }}>
          {typeof diag.body === 'string' ? diag.body : JSON.stringify(diag.body)}
        </code></span>
      )}
      <button
        onClick={() => { sessionStorage.removeItem(AUTH_DIAG_KEY); setDiag(null); }}
        style={{
          marginLeft: 'auto', background: 'none', border: '1px solid rgba(255,255,255,0.7)',
          color: '#fff', cursor: 'pointer', padding: '0.1rem 0.5rem', borderRadius: 3,
          fontFamily: 'inherit', fontSize: 'inherit',
        }}
      >
        Dismiss
      </button>
    </div>
  );
}

// Error component
function ErrorScreen({ message }: { message: string }) {
  return (
    <div style={{ 
      display: 'flex', 
      flexDirection: 'column',
      justifyContent: 'center', 
      alignItems: 'center', 
      height: '100vh',
      fontSize: '1.2rem',
      color: '#d32f2f'
    }}>
      <p>Error: {message}</p>
      <button onClick={() => window.location.reload()} style={{ marginTop: '1rem' }}>
        Retry
      </button>
    </div>
  );
}

// Each sub-site's app, keyed by its base path in SUBSITES (subsites.ts).
const SUBSITE_APPS: Record<string, ComponentType> = {
  '/pass-giveaway': PassGiveawayApp,
  '/directory': DirectoryApp,
};

function App() {
  const { loading, error } = useAuth();

  if (loading) {
    return <><StagingBanner /><AuthDiagBanner /><LoadingScreen /></>;
  }

  if (error) {
    return <><StagingBanner /><AuthDiagBanner /><ErrorScreen message={error} /></>;
  }

  // Each sub-site has its own router, chosen once from the URL: moving between
  // sub-sites is a full page load, so the choice never changes while mounted.
  const subsite = subsiteForPath(window.location.pathname);
  const SubsiteApp = subsite ? SUBSITE_APPS[subsite.basePath] : HomeApp;

  return (
    <>
    <StagingBanner />
    <AuthDiagBanner />
    <SubsiteApp />
    </>
  );
}

export default App;
