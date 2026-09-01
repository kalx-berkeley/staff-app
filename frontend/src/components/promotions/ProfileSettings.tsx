import { useState, useEffect } from 'react';
import { usersAPI } from '../../services/api';
import type { PromotionsStaffProfile, NotificationPreferences, APIError } from '../../types';

const ProfileSettings = () => {
  const [profile, setProfile] = useState<PromotionsStaffProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [notifPrefs, setNotifPrefs] = useState<NotificationPreferences | null>(null);
  const [notifLoading, setNotifLoading] = useState(true);
  const [notifError, setNotifError] = useState<string | null>(null);
  const [notifSaving, setNotifSaving] = useState(false);
  const [notifSaved, setNotifSaved] = useState(false);

  const loadProfile = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await usersAPI.getProfile() as PromotionsStaffProfile;
      setProfile(data);
    } catch (err) {
      const apiError = err as APIError;
      setError(
        typeof apiError.detail === 'string'
          ? apiError.detail
          : 'Failed to load profile'
      );
    } finally {
      setLoading(false);
    }
  };

  const loadNotifPrefs = async () => {
    try {
      setNotifLoading(true);
      setNotifError(null);
      const data = await usersAPI.getNotificationPreferences();
      setNotifPrefs(data);
    } catch (err) {
      const apiError = err as APIError;
      setNotifError(
        typeof apiError.detail === 'string'
          ? apiError.detail
          : 'Failed to load notification settings'
      );
    } finally {
      setNotifLoading(false);
    }
  };

  useEffect(() => {
    loadProfile();
    loadNotifPrefs();
  }, []);

  const handleEmailToggle = async (enabled: boolean) => {
    if (notifSaving) return;
    setNotifSaving(true);
    setNotifError(null);
    setNotifSaved(false);
    try {
      const updated = await usersAPI.updateNotificationPreferences({ email_enabled: enabled });
      setNotifPrefs(updated);
      setNotifSaved(true);
      setTimeout(() => setNotifSaved(false), 2000);
    } catch (err) {
      const apiError = err as APIError;
      setNotifError(
        typeof apiError.detail === 'string'
          ? apiError.detail
          : 'Failed to save notification settings'
      );
    } finally {
      setNotifSaving(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading profile...</div>;
  }

  if (error || !profile) {
    return (
      <div className="error">
        <p>Error: {error || 'Profile not found'}</p>
        <button onClick={loadProfile}>Retry</button>
      </div>
    );
  }

  return (
    <div className="profile-settings">
      <h2>Profile</h2>
      <p className="profile-notice">
        Your profile information is managed in Airtable. To update your name or
        phone number, please edit your record there.
      </p>
      <div className="profile-info">
        <div className="info-item">
          <span className="info-label">Name</span>
          <span className="info-value">{profile.name || '—'}</span>
        </div>
        <div className="info-item">
          <span className="info-label">Phone</span>
          <span className="info-value">{profile.phone || '—'}</span>
        </div>
      </div>

      <h3>Notification Settings</h3>
      {notifLoading ? (
        <div className="loading">Loading notification settings...</div>
      ) : notifPrefs ? (
        <div className="notification-settings">
          {notifError && <div className="error-message">{notifError}</div>}
          {notifSaved && <div className="success-message">Settings saved.</div>}
          <div className="form-group checkbox-group">
            <label>
              <input
                type="checkbox"
                checked={notifPrefs.email_enabled}
                disabled={notifSaving}
                onChange={(e) => handleEmailToggle(e.target.checked)}
              />
              Email notifications enabled
            </label>
          </div>
        </div>
      ) : (
        <div className="error">
          <p>Error: {notifError || 'Could not load notification settings'}</p>
          <button onClick={loadNotifPrefs}>Retry</button>
        </div>
      )}
    </div>
  );
};

export default ProfileSettings;
