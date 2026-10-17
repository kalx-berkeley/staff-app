import { useEffect, useMemo, useState } from 'react';
import { impersonationAPI } from '../common/api';
import PersonAutocomplete from '../common/components/PersonAutocomplete';
import { extractPersonEmail } from '../common/components/personUtils';
import { useAuth } from '../common/contexts/authHooks';
import type { APIError } from '../common/types';
import { adminAPI } from './api';
import type { ImpersonateRequest, UserListItem } from './types';

type ImpersonateMode = 'user' | 'dj' | 'user_dj' | 'station_office';

const MODES: { mode: ImpersonateMode; title: string; description: string }[] = [
  {
    mode: 'user',
    title: 'Impersonate a user',
    description: 'Logged in as a selected user, outside the DJ studio',
  },
  {
    mode: 'dj',
    title: 'Impersonate DJ studio (not logged in)',
    description: 'Request appears to come from the DJ studio network, but no user is logged in',
  },
  {
    mode: 'user_dj',
    title: 'Impersonate a user in the DJ studio',
    description: 'Logged in as a selected user and on the DJ studio network',
  },
  {
    mode: 'station_office',
    title: 'Impersonate station office (not logged in)',
    description:
      'Request appears to come from the station office network (not DJ studio), but no user is logged in',
  },
];

const needsUser = (mode: ImpersonateMode) => mode === 'user' || mode === 'user_dj';

// Staging only: act as another user, or as a guest on the DJ studio or station
// office network, across every sub-site.
export default function ImpersonationSection() {
  const { user } = useAuth();
  const isImpersonating =
    !!user?.impersonating_email ||
    user?.is_impersonating_dj_network ||
    user?.is_impersonating_station_office_network;

  const [userList, setUserList] = useState<UserListItem[]>([]);
  const [userInput, setUserInput] = useState('');
  const [selectedEmail, setSelectedEmail] = useState('');
  const [mode, setMode] = useState<ImpersonateMode>('user');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    adminAPI.listUsers().then(setUserList).catch(() => {});
  }, []);

  const userOptions = useMemo(
    () => userList.map((u) => ({ email: u.email, name: u.name })),
    [userList]
  );

  // Match autocomplete text ("Name (email)" or a bare email) to a listed user
  const resolveUser = (text: string): UserListItem | undefined => {
    const email = extractPersonEmail(text);
    return userList.find((u) => u.email.toLowerCase() === email);
  };

  const handleUserInputChange = (text: string) => {
    setUserInput(text);
    setSelectedEmail(resolveUser(text)?.email ?? '');
  };

  const handleUserInputSubmit = (text: string) => {
    const match = resolveUser(text);
    setUserInput(match ? `${match.name} (${match.email})` : text);
    setSelectedEmail(match?.email ?? '');
  };

  const run = async (action: () => Promise<void>, fallback: string) => {
    setLoading(true);
    setError(null);
    try {
      await action();
      window.location.reload();
    } catch (err) {
      const detail = (err as APIError).detail;
      setError(typeof detail === 'string' ? detail : fallback);
      setLoading(false);
    }
  };

  const handleStart = () => {
    const request: ImpersonateRequest = {
      email: needsUser(mode) ? selectedEmail : null,
      is_dj_network: mode === 'dj' || mode === 'user_dj',
      is_station_office_network: mode === 'station_office',
    };
    run(() => adminAPI.startImpersonation(request), 'Failed to start impersonation');
  };

  return (
    <section className="admin-section">
      <h2>User Impersonation</h2>
      <p className="field-hint">
        Simulate different access contexts to test role-based behavior in every staff site.
      </p>

      {isImpersonating && (
        <div className="impersonate-active">
          <p>
            <strong>Currently impersonating:</strong>{' '}
            {user?.impersonating_email ?? '(not logged in)'}
            {user?.is_impersonating_dj_network && ' + DJ studio network'}
            {user?.is_impersonating_station_office_network && ' + station office network'}
          </p>
          <button
            className="btn-danger"
            onClick={() => run(impersonationAPI.end, 'Failed to end impersonation')}
            disabled={loading}
          >
            End Impersonation
          </button>
        </div>
      )}

      {error && <div className="error-message">{error}</div>}

      <div className="impersonate-choices">
        {MODES.map((choice) => (
          <label
            key={choice.mode}
            className={`impersonate-choice${mode === choice.mode ? ' impersonate-choice--selected' : ''}`}
          >
            <input
              type="radio"
              name="impersonateMode"
              value={choice.mode}
              checked={mode === choice.mode}
              onChange={() => setMode(choice.mode)}
              disabled={loading}
            />
            <span className="impersonate-choice-title">{choice.title}</span>
            <span className="impersonate-choice-desc">{choice.description}</span>
          </label>
        ))}
      </div>

      {needsUser(mode) && userList.length > 0 && (
        <div className="impersonate-user-row">
          <PersonAutocomplete
            ariaLabel="User to impersonate"
            value={userInput}
            onChange={handleUserInputChange}
            onSubmit={handleUserInputSubmit}
            options={userOptions}
            placeholder="Name or email"
            disabled={loading}
          />
        </div>
      )}

      <div className="impersonate-action">
        <button
          className="btn-secondary"
          onClick={handleStart}
          disabled={loading || (needsUser(mode) && !selectedEmail)}
        >
          {loading ? 'Starting…' : 'Start Impersonation'}
        </button>
      </div>
    </section>
  );
}
