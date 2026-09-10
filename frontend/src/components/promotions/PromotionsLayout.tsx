import { useState, useEffect } from 'react';
import { Link, Outlet } from 'react-router-dom';
import { AppNav, BuildInfo } from '../shared';
import { legacyImportAPI } from '../../services/api';

const PromotionsLayout = () => {
  const [navOpen, setNavOpen] = useState(false);
  const [legacyImportEnabled, setLegacyImportEnabled] = useState(false);

  useEffect(() => {
    legacyImportAPI.checkEnabled().then(setLegacyImportEnabled);
  }, []);

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
    <div className="promotions-layout">
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

      <nav className={`promotions-nav${navOpen ? ' nav-is-open' : ''}`}>
        <div className="nav-header">
          <h1>Radio Pass Giveaway</h1>
          <AppNav />
        </div>
        <div className="nav-section-label">Promotions</div>
        <ul className="nav-links nav-sub-links" onClick={() => setNavOpen(false)}>
          <li>
            <Link to="/promotions/shows">Shows</Link>
          </li>
          <li>
            <Link to="/promotions/venues">Venues</Link>
          </li>
          <li>
            <Link to="/promotions/promoters">Promoters</Link>
          </li>
          <li>
            <Link to="/promotions/profile">Profile</Link>
          </li>
          <li>
            <Link to="/promotions/admin">Admin</Link>
          </li>
          {legacyImportEnabled && (
            <li>
              <Link to="/promotions/legacy-import">Legacy Import</Link>
            </li>
          )}
        </ul>

        <div className="nav-build-info">
          <BuildInfo />
        </div>
      </nav>
      <main className="promotions-content">
        <Outlet />
      </main>
    </div>
  );
};

export default PromotionsLayout;
