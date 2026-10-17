import { useState, useEffect } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../../common/contexts/authHooks';
import { AppNav, BuildInfo, ViewBadge } from '../components';
import { legacyImportAPI } from '../api';
import { showsPassGiveawayAdminLink } from '../utils';

const PromotionsLayout = () => {
  const { user } = useAuth();
  const [navOpen, setNavOpen] = useState(false);
  const [legacyImportEnabled, setLegacyImportEnabled] = useState(false);
  // Admins who aren't promotions staff can use only the Admin page
  const isPromotions = user?.role === 'promotions';

  useEffect(() => {
    if (isPromotions) legacyImportAPI.checkEnabled().then(setLegacyImportEnabled);
  }, [isPromotions]);

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
        <ViewBadge />
      </div>

      {navOpen && (
        <div className="nav-overlay" onClick={() => setNavOpen(false)} />
      )}

      <nav className={`promotions-nav${navOpen ? ' nav-is-open' : ''}`}>
        <div className="nav-header">
          <h1>Radio Pass Giveaway</h1>
          <AppNav />
        </div>
        <div className="nav-section-label nav-section-label-promotions">Promotions</div>
        <ul className="nav-links nav-sub-links" onClick={() => setNavOpen(false)}>
          {isPromotions && (
            <>
              <li>
                <NavLink to="/promotions/shows">Shows</NavLink>
              </li>
              <li>
                <NavLink to="/promotions/venues">Venues</NavLink>
              </li>
              <li>
                <NavLink to="/promotions/promoters">Promoters</NavLink>
              </li>
              <li>
                <NavLink to="/promotions/profile">Profile</NavLink>
              </li>
            </>
          )}
          {showsPassGiveawayAdminLink(user) && (
            <li>
              <NavLink to="/promotions/admin">Admin</NavLink>
            </li>
          )}
          {isPromotions && legacyImportEnabled && (
            <li>
              <NavLink to="/promotions/legacy-import">Legacy Import</NavLink>
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
