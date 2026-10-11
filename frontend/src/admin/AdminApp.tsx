import { Suspense } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import LoadingScreen from '../common/components/LoadingScreen';
import { useAuth } from '../common/contexts/authHooks';
import { lazySection } from '../common/lazySection';
import { subsiteForPath } from '../subsites';

const loadAdmin = () => import('.');
const AdminPage = lazySection(loadAdmin, 'AdminPage');

// The KALX Staff Admin sub-site, served under /admin. Anyone who can't use it
// is sent to the home page, which offers what they can use.
export default function AdminApp() {
  const { user } = useAuth();

  if (!subsiteForPath('/admin')?.isAvailable(user)) {
    window.location.replace('/');
    return null;
  }

  return (
    <BrowserRouter basename="/admin">
      <Suspense fallback={<LoadingScreen />}>
        <Routes>
          <Route path="/" element={<AdminPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
