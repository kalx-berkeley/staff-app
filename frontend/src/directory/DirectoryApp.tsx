import { Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import LoadingScreen from '../common/components/LoadingScreen';
import { useAuth } from '../common/contexts/authHooks';
import { lazySection } from '../common/lazySection';
import { subsiteForPath } from '../subsites';

const loadDirectory = () => import('.');
const DirectoryPage = lazySection(loadDirectory, 'DirectoryPage');

// The KALX Staff Directory sub-site, served under /directory. Anyone who can't
// use it is sent to the home page, which offers what they can use.
export default function DirectoryApp() {
  const { user } = useAuth();

  if (!subsiteForPath('/directory')?.isAvailable(user)) {
    window.location.replace('/');
    return null;
  }

  return (
    <BrowserRouter basename="/directory">
      <Suspense fallback={<LoadingScreen />}>
        <Routes>
          <Route path="/" element={<DirectoryPage />} />
          <Route path="/:staffId" element={<DirectoryPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
