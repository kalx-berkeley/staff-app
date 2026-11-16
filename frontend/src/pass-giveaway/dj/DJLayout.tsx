import { useState, useEffect } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { AppNav, BuildInfo, ViewBadge } from '../components';
import SpinMatchNotifier from './SpinMatchNotifier';
import OnAirBanner from './OnAirBanner';
import OnAirProvider from './OnAirProvider';

const DJLayout = () => {
  const [navOpen, setNavOpen] = useState(false);

  useEffect(() => {
    if (!navOpen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setNavOpen(false);
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [navOpen]);

  useEffect(() => {
    document.body.style.overflow = navOpen ? 'hidden' : '';
    return () => { document.body.style.overflow = ''; };
  }, [navOpen]);

  return (
    <OnAirProvider>
    <div className="dj-layout">
      <div className="mobile-topbar">
        <button
          className="hamburger-btn"
          onClick={() => setNavOpen(true)}
          aria-label="Open navigation"
        >
          <span className="hamburger-icon" />
        </button>
        <span className="mobile-title">Radio Pass Giveaway</span>
        <ViewBadge />
      </div>

      {navOpen && (
        <div className="nav-overlay" onClick={() => setNavOpen(false)} />
      )}

      <nav className={`dj-nav${navOpen ? ' nav-is-open' : ''}`}>
        <div className="nav-header">
          <h1>Radio Pass Giveaway</h1>
          <AppNav showGoogleLogout />
        </div>
        <div className="nav-section-label nav-section-label-dj">DJ</div>
        <ul className="nav-links nav-sub-links" onClick={() => setNavOpen(false)}>
          <li>
            <NavLink to="/dj/shows">Shows</NavLink>
          </li>
          <li>
            <NavLink to="/dj/my-passes">My Passes</NavLink>
          </li>
          <li>
            <NavLink to="/dj/winner-search">Winner Search</NavLink>
          </li>
        </ul>

        <div className="nav-build-info">
          <BuildInfo />
        </div>
      </nav>
      <main className="dj-content">
        <OnAirBanner />
        <Outlet />
      </main>
      <SpinMatchNotifier />
    </div>
    </OnAirProvider>
  );
};

export default DJLayout;
