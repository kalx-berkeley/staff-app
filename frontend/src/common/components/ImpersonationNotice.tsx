import { useState } from 'react';
import { impersonationAPI } from '../api';
import { useAuth } from '../contexts/authHooks';

// Who a staging impersonation is acting as, with a button to end it. Shown in
// the header of the sub-sites without their own impersonation display (the
// pass giveaway's AppNav has one).
const ImpersonationNotice = () => {
  const { user } = useAuth();
  const [ending, setEnding] = useState(false);

  const targets = [
    user?.impersonating_email,
    user?.is_impersonating_dj_network && 'the DJ studio network',
    user?.is_impersonating_station_office_network && 'the station office network',
  ].filter(Boolean);
  if (targets.length === 0) return null;

  const handleEnd = async () => {
    setEnding(true);
    try {
      await impersonationAPI.end();
    } finally {
      window.location.reload();
    }
  };

  return (
    <p className="impersonation-notice">
      Viewing as {targets.join(' on ')}{' '}
      <button className="btn-secondary btn-small" onClick={handleEnd} disabled={ending}>
        {ending ? 'Ending…' : 'End impersonation'}
      </button>
    </p>
  );
};

export default ImpersonationNotice;
