import { useState, useEffect } from 'react';
import { Link, Outlet } from 'react-router-dom';
import { AppNav, BuildInfo } from '../shared';
import { useAuth } from '../../contexts/authHooks';
import { specialtyShowsAPI } from '../../services/api';
import type { SpecialtyShowResponse } from '../../types';

const StaffLayout = () => {
  const [navOpen, setNavOpen] = useState(false);
  const { user } = useAuth();
  const profile = user?.profile;
  const isSublistDj = profile && 'is_sublist_dj' in profile && profile.is_sublist_dj;
  const [mySpecialtyShows, setMySpecialtyShows] = useState<SpecialtyShowResponse[]>([]);

  useEffect(() => {
    if (user?.role === 'staff' || user?.role === 'promotions') {
      specialtyShowsAPI.listMy().then(setMySpecialtyShows).catch(() => {});
    }
  }, [user]);

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
    <div className="staff-layout">
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

      <nav className={`staff-nav${navOpen ? ' nav-is-open' : ''}`}>
        <div className="nav-header">
          <h1>Radio Pass Giveaway</h1>
          <AppNav />
        </div>
        <div className="nav-section-label">Staff</div>
        <ul className="nav-links nav-sub-links" onClick={() => setNavOpen(false)}>
          <li>
            <Link to="/staff/shows">Shows</Link>
          </li>
          {isSublistDj && (
            <li>
              <Link to="/staff/my-passes">My Passes</Link>
            </li>
          )}
          {(user?.role === 'promotions' || mySpecialtyShows.length > 0) && (
            <li>
              <Link to="/staff/specialty-shows">Specialty Shows</Link>
            </li>
          )}
          <li>
            <Link to="/staff/profile">Profile</Link>
          </li>
        </ul>

        <div className="nav-build-info">
          <BuildInfo />
        </div>
      </nav>
      <main className="staff-content">
        <Outlet />
      </main>
    </div>
  );
};

export default StaffLayout;
