import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../contexts/authHooks';
import { adminAPI } from '../../services/api';
import FeedbackModal from './FeedbackModal';
import BuildInfo from './BuildInfo';

const ROLE_LABELS: Record<string, string> = {
  promotions: 'Promotions Staff',
  staff: 'Staff Member',
  dj: 'DJ',
};

const LockIcon = () => (
  <svg
    width="10"
    height="12"
    viewBox="0 0 10 12"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
    className="nav-lock-icon"
  >
    <rect x="1" y="5" width="8" height="7" rx="1" stroke="currentColor" strokeWidth="1.5" />
    <path d="M2.5 5V3.5a2.5 2.5 0 015 0V5" stroke="currentColor" strokeWidth="1.5" />
  </svg>
);

interface LockedViewProps {
  label: string;
  tooltip: string;
}

const LockedView = ({ label, tooltip }: LockedViewProps) => (
  <span className="tooltip-wrapper app-nav-view-locked">
    <span className="app-nav-view-locked-inner">
      {label}
      <LockIcon />
    </span>
    <span className="tooltip-box" role="tooltip">
      {tooltip}
    </span>
  </span>
);

interface AppNavProps {
  showGoogleLogout?: boolean;
}

const AppNav = ({ showGoogleLogout = false }: AppNavProps) => {
  const { user, refetchUser } = useAuth();
  const [showFeedback, setShowFeedback] = useState(false);

  const handleEndImpersonation = async () => {
    await adminAPI.endImpersonation();
    await refetchUser();
  };

  const handleGoogleLogout = () => {
    const newWindow = window.open(
      'https://mail.google.com/mail/?logout&hl=fr',
      'Disconnect from Google',
      'width=100,height=50,menubar=no,status=no,location=no,toolbar=no,scrollbars=no,top=200,left=200'
    );
    setTimeout(() => {
      if (newWindow) newWindow.close();
      window.location.href = 'auth/google';
    }, 3000);
  };

  const canAccessPromotions = user?.role === 'promotions';
  const canAccessStaff = user?.role === 'staff' || user?.role === 'promotions';
  const canAccessDJ =
    user?.role === 'dj' ||
    user?.role === 'promotions' ||
    user?.is_dj_network === true;

  const email = user?.email ?? 'DJ Guest';
  const roleLabel = (user?.role && ROLE_LABELS[user.role]) ?? 'Guest';

  const isImpersonating =
    !!user?.impersonating_email ||
    user?.is_impersonating_dj_network ||
    user?.is_impersonating_station_office_network;

  return (
    <div className="app-nav">
      <div className="app-nav-user">
        {isImpersonating ? (
          <div className="impersonation-block">
            <div className="impersonation-block-header">
              <span className="impersonation-tag">Impersonating</span>
              <button
                className="btn-end-impersonation"
                onClick={handleEndImpersonation}
                title={`End impersonation of ${user?.impersonating_email ?? 'DJ Network'}`}
              >
                End
              </button>
            </div>
            <div className="impersonation-real" title={user?.real_email ?? undefined}>
              {user?.real_email}
            </div>
            {user?.impersonating_email && (
              <div className="impersonation-target" title={user.impersonating_email}>
                {user.impersonating_email}
              </div>
            )}
            {user?.is_impersonating_dj_network && (
              <div className="impersonation-target">
                {user?.impersonating_email ? '+DJ Network' : 'DJ Network'}
              </div>
            )}
            {user?.is_impersonating_station_office_network && (
              <div className="impersonation-target">
                Station Office Network
              </div>
            )}
          </div>
        ) : (
          <span className="user-email" title={email}>{email}</span>
        )}
        {showGoogleLogout && user?.is_dj_network && user?.email && (
          <button
            className="google-logout-link"
            onClick={handleGoogleLogout}
            title="Sign out of Google"
          >
            Sign out of Google
          </button>
        )}
        <span className="role-badge" title="Your account role">{roleLabel}</span>
      </div>
      <ul className="app-nav-views">
        <li>
          {canAccessPromotions ? (
            <Link to="/promotions/shows" className="app-nav-view-link">Promotions</Link>
          ) : (
            <LockedView label="Promotions" tooltip="Only accessible to users with the Promotions Staff role." />
          )}
        </li>
        <li>
          {canAccessStaff ? (
            <Link to="/staff/shows" className="app-nav-view-link">Staff</Link>
          ) : (
            <LockedView label="Staff" tooltip="Only accessible to users with the Staff or Promotions Staff role." />
          )}
        </li>
        <li>
          {canAccessDJ ? (
            <Link to="/dj/shows" className="app-nav-view-link">DJ</Link>
          ) : (
            <LockedView label="DJ" tooltip="Only accessible to users with the DJ role or when connected from the KALX studio network." />
          )}
        </li>
      </ul>
      <div className="app-nav-feedback">
        <button
          className="feedback-link"
          onClick={() => setShowFeedback(true)}
        >
          Send Feedback / Report a Bug
        </button>
        <BuildInfo />
      </div>
      {showFeedback && (
        <FeedbackModal onClose={() => setShowFeedback(false)} />
      )}
    </div>
  );
};

export default AppNav;
