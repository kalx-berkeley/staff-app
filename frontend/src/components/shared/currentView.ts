import { useLocation } from 'react-router-dom';

// The three role views the app is divided into. Every page lives under one of
// these path prefixes — see the <Routes> tree in App.tsx.
export type AppView = 'promotions' | 'staff' | 'dj';

export const VIEW_LABELS: Record<AppView, string> = {
  promotions: 'Promotions',
  staff: 'Staff',
  dj: 'DJ',
};

// Which role view the current URL belongs to, or null for the handful of
// pages outside the three views (e.g. /unauthorized). Drives the current-view
// highlight in AppNav and the badge in the mobile top bar.
export function useCurrentView(): AppView | null {
  const { pathname } = useLocation();
  const segment = pathname.split('/')[1];
  if (segment === 'promotions' || segment === 'staff' || segment === 'dj') {
    return segment;
  }
  return null;
}
