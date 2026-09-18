import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { usersAPI, showsAPI, specialtyShowsAPI } from '../../services/api';
import GenreTagInput from './GenreTagInput';
import { usePageTitle } from '../../hooks/usePageTitle';
import type {
  PromotionsStaffProfile,
  StaffProfile,
  NotificationPreferences,
  MySpecialtyShowResponse,
  APIError,
} from '../../types';

// Rendered at both /promotions/profile and /staff/profile; the caller says
// which section it's mounted under so the page title can name it.
const ProfileSettings = ({ section }: { section: 'Promotions' | 'Staff' }) => {
  usePageTitle(`Profile · ${section}`);
  const [profile, setProfile] = useState<PromotionsStaffProfile | StaffProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [notifPrefs, setNotifPrefs] = useState<NotificationPreferences | null>(null);
  const [notifLoading, setNotifLoading] = useState(true);
  const [notifError, setNotifError] = useState<string | null>(null);
  const [notifSaving, setNotifSaving] = useState(false);
  const [notifSaved, setNotifSaved] = useState(false);

  const [knownGenres, setKnownGenres] = useState<string[]>([]);
  const [genrePrefs, setGenrePrefs] = useState<string[]>([]);
  const [genrePrefsLoading, setGenrePrefsLoading] = useState(true);
  const [genrePrefsError, setGenrePrefsError] = useState<string | null>(null);
  const [genrePrefsSaving, setGenrePrefsSaving] = useState(false);
  const [genrePrefsSaved, setGenrePrefsSaved] = useState(false);

  const [specialtyShows, setSpecialtyShows] = useState<MySpecialtyShowResponse[]>([]);
  const [specialtyShowsLoading, setSpecialtyShowsLoading] = useState(true);
  const [specialtyShowsError, setSpecialtyShowsError] = useState<string | null>(null);

  const loadProfile = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await usersAPI.getProfile();
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

  const loadGenrePrefs = async () => {
    try {
      setGenrePrefsLoading(true);
      setGenrePrefsError(null);
      const data = await usersAPI.getGenrePreferences();
      setGenrePrefs(data.genres);
    } catch (err) {
      const apiError = err as APIError;
      setGenrePrefsError(
        typeof apiError.detail === 'string'
          ? apiError.detail
          : 'Failed to load genre preferences'
      );
    } finally {
      setGenrePrefsLoading(false);
    }
  };

  const loadSpecialtyShows = async () => {
    try {
      setSpecialtyShowsLoading(true);
      setSpecialtyShowsError(null);
      const data = await specialtyShowsAPI.listMine();
      setSpecialtyShows(data);
    } catch (err) {
      const apiError = err as APIError;
      setSpecialtyShowsError(
        typeof apiError.detail === 'string'
          ? apiError.detail
          : 'Failed to load specialty shows'
      );
    } finally {
      setSpecialtyShowsLoading(false);
    }
  };

  useEffect(() => {
    loadProfile();
    loadNotifPrefs();
    loadGenrePrefs();
    loadSpecialtyShows();
    showsAPI.listGenres().then(setKnownGenres).catch(() => {});
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

  const handleGenresChange = async (genres: string[]) => {
    if (genrePrefsSaving) return;
    const previous = genrePrefs;
    setGenrePrefsSaving(true);
    setGenrePrefsError(null);
    setGenrePrefsSaved(false);
    setGenrePrefs(genres);
    try {
      const updated = await usersAPI.updateGenrePreferences({ genres });
      setGenrePrefs(updated.genres);
      setGenrePrefsSaved(true);
      setTimeout(() => setGenrePrefsSaved(false), 2000);
    } catch (err) {
      setGenrePrefs(previous);
      const apiError = err as APIError;
      setGenrePrefsError(
        typeof apiError.detail === 'string'
          ? apiError.detail
          : 'Failed to save genre preferences'
      );
    } finally {
      setGenrePrefsSaving(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading profile...</div>;
  }

  if (error || !profile) {
    return (
      <div className="error">
        <p>Error: {error || 'Profile not found'}</p>
        <button onClick={loadProfile} className="btn-primary">Retry</button>
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
          <p className="field-hint">
            When enabled, you'll receive emails for:
          </p>
          <ul className="field-hint">
            <li>Lottery results — whether you won or lost a pass (or on-air pass pair) lottery you entered</li>
            <li>Lottery entry cancellations — if a show you entered a lottery for is cancelled before the drawing</li>
            <li>
              Venue owner alerts, if you manage a venue — show cancellations, pass count
              reductions affecting assigned or claimed passes, auto-closed show guest
              lists, reminders for shows not yet closed after their date, and pass
              winner releases
            </li>
          </ul>
          <p className="field-hint">
            Disabling this stops all of the above; you'll need to check the app directly instead.
          </p>
        </div>
      ) : (
        <div className="error">
          <p>Error: {notifError || 'Could not load notification settings'}</p>
          <button onClick={loadNotifPrefs} className="btn-primary">Retry</button>
        </div>
      )}

      <h3>Genres You Like</h3>
      {genrePrefsLoading ? (
        <div className="loading">Loading genre preferences...</div>
      ) : (
        <div className="genre-preferences">
          {genrePrefsError && <div className="error-message">{genrePrefsError}</div>}
          {genrePrefsSaved && <div className="success-message">Saved.</div>}
          <p className="field-hint">
            Pick genres you enjoy. If you're a Sublist DJ, promotions staff use this
            to suggest you (and specialty shows you're part of) when pre-assigning
            pass pairs to shows in these genres.
          </p>
          <label htmlFor="genre-preferences-input">Genres</label>
          <p className="field-hint">
            Type a genre, then press Enter or comma to add it and start the next one.
          </p>
          <GenreTagInput
            genres={genrePrefs}
            onChange={handleGenresChange}
            knownGenres={knownGenres}
            disabled={genrePrefsSaving}
            id="genre-preferences-input"
          />
        </div>
      )}

      <h3>Specialty Shows</h3>
      {specialtyShowsLoading ? (
        <div className="loading">Loading specialty shows...</div>
      ) : specialtyShowsError ? (
        <div className="error">
          <p>Error: {specialtyShowsError}</p>
          <button onClick={loadSpecialtyShows} className="btn-primary">Retry</button>
        </div>
      ) : specialtyShows.length === 0 ? (
        <p className="field-hint">
          You're not an owner or DJ on any specialty shows.
        </p>
      ) : (
        <ul className="profile-specialty-shows">
          {specialtyShows.map((show) => (
            <li key={show.id} className="profile-specialty-show-item">
              <Link to={`/staff/specialty-shows/${show.id}`}>{show.name}</Link>
              <span className="profile-specialty-show-roles">
                {show.is_owner && <span className="specialty-show-badge">Owner</span>}
                {show.is_dj && <span className="dj-name-badge">DJ</span>}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default ProfileSettings;
