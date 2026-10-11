import { useEffect, useState } from 'react';
import { usePageTitle } from '../common/hooks/usePageTitle';
import { workformsAPI } from './api';
import type { Preferences } from './types';
import { errorMessage } from './utils';
import { WORKFORMS_TITLE } from './WorkformsLayout';

// Which workforms emails the user gets. Department heads don't fill in
// workforms, so they're offered the review email rather than reminders.
export default function SettingsPage() {
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  usePageTitle('Settings', WORKFORMS_TITLE);

  useEffect(() => {
    workformsAPI
      .preferences()
      .then(setPrefs)
      .catch((e) => setError(errorMessage(e)));
  }, []);

  if (error && !prefs) return <div className="error-message">{error}</div>;
  if (!prefs) return <p className="workforms-loading">Loading…</p>;

  const change = async (
    field: 'reminder_emails_enabled' | 'review_emails_enabled',
    value: boolean
  ) => {
    setSaved(false);
    try {
      setPrefs(
        await workformsAPI.updatePreferences({
          reminder_emails_enabled: prefs.reminder_emails_enabled,
          review_emails_enabled: prefs.review_emails_enabled,
          [field]: value,
        })
      );
      setError(null);
      setSaved(true);
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  return (
    <section className="workforms-card workforms-settings">
      <h2>Email settings</h2>
      {prefs.is_department_head ? (
        <label>
          <input
            type="checkbox"
            checked={prefs.review_emails_enabled}
            onChange={(e) => change('review_emails_enabled', e.target.checked)}
          />{' '}
          Email me on the 6th of each month when workforms are waiting for my review
        </label>
      ) : (
        <label>
          <input
            type="checkbox"
            checked={prefs.reminder_emails_enabled}
            onChange={(e) => change('reminder_emails_enabled', e.target.checked)}
          />{' '}
          Remind me to submit my workform (on the last day of the month, and on the 3rd if I still
          haven't)
        </label>
      )}
      {saved && (
        <p className="workforms-hint" role="status">
          Saved.
        </p>
      )}
      {error && (
        <div className="error-message" role="alert">
          {error}
        </div>
      )}
    </section>
  );
}
