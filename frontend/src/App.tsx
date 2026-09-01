import { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import UnauthorizedPage from './components/UnauthorizedPage';
import {
  PromotionsLayout,
  ShowList,
  ShowForm,
  ShowDetail as PromotionsShowDetail,
  VenueList,
  VenueNew,
  VenueEdit,
  ProfileSettings as PromotionsProfileSettings,
  Admin,
  PromoterList,
  PromoterNew,
  PromoterEdit,
  LegacyImport,
} from './components/promotions';
import {
  StaffLayout,
  ShowBrowser as StaffShowBrowser,
  ShowDetail as StaffShowDetail,
  ProfileSettings as StaffProfileSettings,
  MyPasses as StaffMyPasses,
  SpecialtyShowList as StaffSpecialtyShowList,
  SpecialtyShowDetail as StaffSpecialtyShowDetail,
} from './components/staff';
import {
  DJLayout,
  ShowBrowser as DJShowBrowser,
  ShowDetail as DJShowDetail,
  MyPasses,
  WinnerSearch,
  GiveawayPage,
} from './components/dj';
import { useAuth } from './contexts/authHooks';
import { AUTH_DIAG_KEY } from './services/api';

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
      position: 'fixed', top: 0, left: 0, right: 0, zIndex: 9999,
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
// users, authenticated promotions staff, and authenticated staff on either network.
// Individual child routes that need DJ-network-only access use DJNetworkOnlyRoute.
function DJProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();

  if (!user) return <DJAccessDenied />;
  if (user.role === 'unauthorized') return <Navigate to="/unauthorized" replace />;

  const canAccess =
    (user.role === 'dj' && (user.is_dj_network || user.is_station_office_network)) ||
    user.role === 'promotions' ||
    (user.role === 'staff' && (user.is_dj_network || user.is_station_office_network));

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
    (user.role === 'staff' && user.is_dj_network);

  if (!canAccess) return <DJAccessDenied />;

  return <>{children}</>;
}

function App() {
  const { loading, error } = useAuth();

  if (loading) {
    return <><AuthDiagBanner /><LoadingScreen /></>;
  }

  if (error) {
    return <><AuthDiagBanner /><ErrorScreen message={error} /></>;
  }

  return (
    <>
    <AuthDiagBanner />
    <BrowserRouter basename="/pass-giveaway">
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
          <Route path="profile" element={<PromotionsProfileSettings />} />
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
          <Route path="profile" element={<StaffProfileSettings />} />
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
    </BrowserRouter>
    </>
  );
}

export default App;
