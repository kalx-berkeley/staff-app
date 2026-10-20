import { Suspense } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import LoadingScreen from '../common/components/LoadingScreen';
import { useAuth } from '../common/contexts/authHooks';
import { lazySection } from '../common/lazySection';
import { subsiteForPath } from '../subsites';
import WorkformsLayout from './WorkformsLayout';

const loadWorkforms = () => import('.');
const MonthPage = lazySection(loadWorkforms, 'MonthPage');
const HistoryPage = lazySection(loadWorkforms, 'HistoryPage');
const ReviewPage = lazySection(loadWorkforms, 'ReviewPage');
const PeoplePage = lazySection(loadWorkforms, 'PeoplePage');
const SettingsPage = lazySection(loadWorkforms, 'SettingsPage');

// The KALX Workforms sub-site, served under /workforms. Anyone who can't use
// it is sent to the home page, which offers what they can use.
export default function WorkformsApp() {
  const { user } = useAuth();

  if (!subsiteForPath('/workforms')?.isAvailable(user)) {
    window.location.replace('/');
    return null;
  }

  return (
    <BrowserRouter basename="/workforms">
      <WorkformsLayout>
        <Suspense fallback={<LoadingScreen />}>
          <Routes>
            <Route path="/" element={<MonthPage />} />
            <Route path="/month/:month" element={<MonthPage />} />
            <Route path="/history" element={<HistoryPage />} />
            {user?.is_department_head && (
              <>
                <Route path="/review" element={<ReviewPage />} />
                <Route path="/review/:month" element={<ReviewPage />} />
                <Route path="/people" element={<PeoplePage />} />
              </>
            )}
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </WorkformsLayout>
    </BrowserRouter>
  );
}
