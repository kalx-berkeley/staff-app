import { Suspense } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import LoadingScreen from '../common/components/LoadingScreen';
import { useAuth } from '../common/contexts/authHooks';
import { lazySection } from '../common/lazySection';
import { subsiteForPath } from '../subsites';

const loadAnalytics = () => import('.');
const AnalyticsLayout = lazySection(loadAnalytics, 'AnalyticsLayout');
const OverviewPage = lazySection(loadAnalytics, 'OverviewPage');
const VenuesPage = lazySection(loadAnalytics, 'VenuesPage');
const VenuePage = lazySection(loadAnalytics, 'VenuePage');
const DjsPage = lazySection(loadAnalytics, 'DjsPage');
const DjPage = lazySection(loadAnalytics, 'DjPage');
const RepsPage = lazySection(loadAnalytics, 'RepsPage');
const ShortLinksPage = lazySection(loadAnalytics, 'ShortLinksPage');
const UsagePage = lazySection(loadAnalytics, 'UsagePage');

// The KALX Staff Analytics sub-site, served under /analytics, for site admins
// and promotions admins. Anyone else is sent to the home page.
export default function AnalyticsApp() {
  const { user } = useAuth();

  if (!subsiteForPath('/analytics')?.isAvailable(user)) {
    window.location.replace('/');
    return null;
  }

  return (
    <BrowserRouter basename="/analytics">
      <Suspense fallback={<LoadingScreen />}>
        <Routes>
          <Route element={<AnalyticsLayout />}>
            <Route path="/" element={<OverviewPage />} />
            <Route path="/venues" element={<VenuesPage />} />
            <Route path="/venues/:venueId" element={<VenuePage />} />
            <Route path="/djs" element={<DjsPage />} />
            <Route path="/djs/:djKey" element={<DjPage />} />
            <Route path="/reps" element={<RepsPage />} />
            <Route path="/short-links" element={<ShortLinksPage />} />
            <Route path="/usage" element={<UsagePage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
