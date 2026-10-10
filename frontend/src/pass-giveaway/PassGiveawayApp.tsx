import { Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import LoadingScreen from '../common/components/LoadingScreen';
import UnauthorizedPage from '../common/components/UnauthorizedPage';
import { useAuth } from '../common/contexts/authHooks';
import { lazySection } from '../common/lazySection';
import ProfileSettings from './components/ProfileSettings';
import { isStagingSublistDjStaff } from './utils';

// Each role's section (promotions, staff, dj) is its own lazily loaded chunk;
// see lazySection.
const loadPromotions = () => import('./promotions');
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

const loadStaff = () => import('./staff');
const StaffLayout = lazySection(loadStaff, 'StaffLayout');
const StaffShowBrowser = lazySection(loadStaff, 'ShowBrowser');
const StaffShowDetail = lazySection(loadStaff, 'ShowDetail');
const StaffMyPasses = lazySection(loadStaff, 'MyPasses');
const StaffSpecialtyShowList = lazySection(loadStaff, 'SpecialtyShowList');
const StaffSpecialtyShowDetail = lazySection(loadStaff, 'SpecialtyShowDetail');

const loadDJ = () => import('./dj');
const DJLayout = lazySection(loadDJ, 'DJLayout');
const DJShowBrowser = lazySection(loadDJ, 'ShowBrowser');
const DJShowDetail = lazySection(loadDJ, 'ShowDetail');
const MyPasses = lazySection(loadDJ, 'MyPasses');
const WinnerSearch = lazySection(loadDJ, 'WinnerSearch');
const GiveawayPage = lazySection(loadDJ, 'GiveawayPage');

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

// The Radio Pass Giveaway sub-site, served under /pass-giveaway. Its routes
// and links are relative to that basename.
export default function PassGiveawayApp() {
  return (
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
  );
}
