import { lazy, Suspense, useState, type ComponentType } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import UnauthorizedPage from './components/UnauthorizedPage';

// Each role's section is code-split into its own chunk so users only download
// the pages for the section they use. Components are loaded through their
// section's barrel so a whole section shares one chunk, and navigating within
// a section doesn't suspend again after the first load.
function lazySection<M, K extends keyof M>(load: () => Promise<M>, name: K) {
  return lazy(() => load().then((m) => ({ default: m[name] as ComponentType })));
}

const loadPromotions = () => import('./components/promotions');
const PromotionsLayout = lazySection(loadPromotions, 'PromotionsLayout');
const ShowList = lazySection(loadPromotions, 'ShowList');
const ShowForm = lazySection(loadPromotions, 'ShowForm');
const PromotionsShowDetail = lazySection(loadPromotions, 'ShowDetail');
const VenueList = lazySection(loadPromotions, 'VenueList');
const VenueNew = lazySection(loadPromotions, 'VenueNew');
const VenueEdit = lazySection(loadPromotions, 'VenueEdit');
const Admin = lazySection(loadPromotions, 'Admin');
const PromoterList = lazySection(loadPromotions, 'PromoterList');
const PromoterNew = lazySection(loadPromotions, 'PromoterNew');
const PromoterEdit = lazySection(loadPromotions, 'PromoterEdit');
const LegacyImport = lazySection(loadPromotions, 'LegacyImport');

const loadStaff = () => import('./components/staff');
const StaffLayout = lazySection(loadStaff, 'StaffLayout');
const StaffShowBrowser = lazySection(loadStaff, 'ShowBrowser');
const StaffShowDetail = lazySection(loadStaff, 'ShowDetail');
const StaffMyPasses = lazySection(loadStaff, 'MyPasses');
const StaffSpecialtyShowList = lazySection(loadStaff, 'SpecialtyShowList');
const StaffSpecialtyShowDetail = lazySection(loadStaff, 'SpecialtyShowDetail');

const loadDJ = () => import('./components/dj');
const DJLayout = lazySection(loadDJ, 'DJLayout');
const DJShowBrowser = lazySection(loadDJ, 'ShowBrowser');
const DJShowDetail = lazySection(loadDJ, 'ShowDetail');
const MyPasses = lazySection(loadDJ, 'MyPasses');
const WinnerSearch = lazySection(loadDJ, 'WinnerSearch');
const GiveawayPage = lazySection(loadDJ, 'GiveawayPage');

import { useAuth } from './contexts/authHooks';
import { AUTH_DIAG_KEY } from './services/api';
import { isStagingEnvironment, isStagingSublistDjStaff } from './utils';
import StagingBanner from './components/shared/StagingBanner';
import ProfileSettings from './components/shared/ProfileSettings';

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

// Loading component
function LoadingScreen() {
  return (
    <div style={{ 
      display: 'flex', 
      justifyContent: 'center', 
      alignItems: 'center', 
      height: '100vh',
      fontSize: '1.5rem'
    }}>
      Loading...
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

// Role-based redirect component
function RoleBasedRedirect() {
  const { user } = useAuth();

  if (!user) {
    return <Navigate to="/dj/shows" replace />;
  }

  switch (user.role) {
    case 'promotions':
      return <Navigate to="/promotions/shows" replace />;
    case 'staff':
      return <Navigate to="/staff/shows" replace />;
    case 'dj':
      return <Navigate to={user.is_dj_network ? "/dj/shows" : "/dj/winner-search"} replace />;
    case 'unauthorized':
      return <Navigate to="/unauthorized" replace />;
    default:
      return <Navigate to="/dj/shows" replace />;
  }
}

// Protected route wrapper
function ProtectedRoute({
  children,
  allowedRoles
}: {
  children: React.ReactNode;
  allowedRoles: string[];
}) {
  const { user } = useAuth();

  if (!user) {
    return <RoleBasedRedirect />;
  }

  if (!allowedRoles.includes(user.role)) {
    return <RoleBasedRedirect />;
  }

  return <>{children}</>;
}

// Shown when accessing the DJ view without the right network access or role
function DJAccessDenied() {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      alignItems: 'center',
      height: '100vh',
      fontSize: '1.1rem',
      textAlign: 'center',
      padding: '2rem',
    }}>
      <h2>DJ View Access Required</h2>
      <p>This page is only accessible from the KALX air studio network,<br />
         or when logged in as promotions staff.</p>
    </div>
  );
}

// DJ route wrapper — allows unauthenticated DJ-network or station-office-network
// users, authenticated promotions staff, authenticated staff on either network,
// and (in staging only) staff with Sublist DJ status.
// Individual child routes that need DJ-network-only access use DJNetworkOnlyRoute.
function DJProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();

  if (!user) return <DJAccessDenied />;
  if (user.role === 'unauthorized') return <Navigate to="/unauthorized" replace />;

  const canAccess =
    (user.role === 'dj' && (user.is_dj_network || user.is_station_office_network)) ||
    user.role === 'promotions' ||
    (user.role === 'staff' && (user.is_dj_network || user.is_station_office_network)) ||
    isStagingSublistDjStaff(user);

  if (!canAccess) return <DJAccessDenied />;

  return <>{children}</>;
}

// Inner wrapper for DJ routes that require the DJ studio network specifically
// (shows, my-passes). Does not apply to winner-search.
function DJNetworkOnlyRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();

  if (!user) return <DJAccessDenied />;

  const canAccess =
    (user.role === 'dj' && user.is_dj_network) ||
    user.role === 'promotions' ||
    (user.role === 'staff' && user.is_dj_network) ||
    isStagingSublistDjStaff(user);

  if (!canAccess) return <DJAccessDenied />;

  return <>{children}</>;
}

function App() {
  const { loading, error } = useAuth();

  if (loading) {
    return <><StagingBanner /><AuthDiagBanner /><LoadingScreen /></>;
  }

  if (error) {
    return <><StagingBanner /><AuthDiagBanner /><ErrorScreen message={error} /></>;
  }

  return (
    <>
    <StagingBanner />
    <AuthDiagBanner />
    <BrowserRouter basename="/pass-giveaway">
      <Suspense fallback={<LoadingScreen />}>
      <Routes>
        {/* Default redirect based on role */}
        <Route path="/" element={<RoleBasedRedirect />} />

        {/* Promotions staff routes */}
        <Route 
          path="/promotions" 
          element={
            <ProtectedRoute allowedRoles={['promotions']}>
              <PromotionsLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/promotions/shows" replace />} />
          <Route path="shows" element={<ShowList />} />
          <Route path="shows/new" element={<ShowForm />} />
          <Route path="shows/:id" element={<PromotionsShowDetail />} />
          <Route path="shows/:id/edit" element={<ShowForm />} />
          <Route path="venues/new" element={<VenueNew />} />
          <Route path="venues/:id/edit" element={<VenueEdit />} />
          <Route path="venues" element={<VenueList />} />
          <Route path="promoters/new" element={<PromoterNew />} />
          <Route path="promoters/:id/edit" element={<PromoterEdit />} />
          <Route path="promoters" element={<PromoterList />} />
          <Route path="profile" element={<ProfileSettings section="Promotions" />} />
          <Route path="admin" element={<Admin />} />
          <Route path="legacy-import" element={<LegacyImport />} />
        </Route>

        {/* Staff member routes */}
        <Route
          path="/staff"
          element={
            <ProtectedRoute allowedRoles={['staff', 'promotions']}>
              <StaffLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/staff/shows" replace />} />
          <Route path="shows" element={<StaffShowBrowser />} />
          <Route path="shows/:id" element={<StaffShowDetail />} />
          <Route path="my-passes" element={<StaffMyPasses />} />
          <Route path="specialty-shows" element={<StaffSpecialtyShowList />} />
          <Route path="specialty-shows/:id" element={<StaffSpecialtyShowDetail />} />
          <Route path="profile" element={<ProfileSettings section="Staff" />} />
        </Route>

        {/* DJ routes - accessible from DJ studio network or as promotions staff */}
        <Route
          path="/dj"
          element={
            <DJProtectedRoute>
              <DJLayout />
            </DJProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/dj/shows" replace />} />
          <Route path="shows" element={<DJNetworkOnlyRoute><DJShowBrowser /></DJNetworkOnlyRoute>} />
          <Route path="shows/:id" element={<DJNetworkOnlyRoute><DJShowDetail /></DJNetworkOnlyRoute>} />
          <Route path="shows/:id/giveaway" element={<DJNetworkOnlyRoute><GiveawayPage /></DJNetworkOnlyRoute>} />
          <Route path="my-passes" element={<DJNetworkOnlyRoute><MyPasses /></DJNetworkOnlyRoute>} />
          <Route path="winner-search" element={<WinnerSearch />} />
        </Route>

        {/* Unauthorized Google users */}
        <Route path="/unauthorized" element={<UnauthorizedPage />} />

        {/* Catch-all route - redirect based on role */}
        <Route path="*" element={<RoleBasedRedirect />} />
      </Routes>
      </Suspense>
    </BrowserRouter>
    </>
  );
}

export default App;
