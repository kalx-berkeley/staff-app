import { useState, useEffect } from 'react';
import { Link, Outlet } from 'react-router-dom';
import { AppNav, BuildInfo } from '../shared';
import SpinMatchNotifier from './SpinMatchNotifier';

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
      </div>

      {navOpen && (
        <div className="nav-overlay" onClick={() => setNavOpen(false)} />
      )}

      <nav className={`dj-nav${navOpen ? ' nav-is-open' : ''}`}>
        <div className="nav-header">
          <h1>Radio Pass Giveaway</h1>
          <AppNav showGoogleLogout />
        </div>
        <div className="nav-section-label">DJ</div>
        <ul className="nav-links nav-sub-links" onClick={() => setNavOpen(false)}>
          <li>
            <Link to="/dj/shows">Shows</Link>
          </li>
          <li>
            <Link to="/dj/my-passes">My Passes</Link>
          </li>
          <li>
            <Link to="/dj/winner-search">Winner Search</Link>
          </li>
        </ul>

        <div className="nav-build-info">
          <BuildInfo />
        </div>
      </nav>
      <main className="dj-content">
        <Outlet />
      </main>
      <SpinMatchNotifier />
    </div>
  );
};

export default DJLayout;
