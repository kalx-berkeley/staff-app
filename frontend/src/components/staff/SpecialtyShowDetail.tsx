import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { specialtyShowsAPI, autocompleteAPI } from '../../services/api';
import { useAuth } from '../../contexts/authHooks';
import { usePageTitle } from '../../hooks/usePageTitle';
import { PersonAutocomplete, extractPersonEmail } from '../shared';
import type { SpecialtyShowResponse, SpecialtyShowOwnerInfo, APIError } from '../../types';

const SpecialtyShowDetail = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [show, setShow] = useState<SpecialtyShowResponse | null>(null);
  usePageTitle(`${show?.name ?? 'Specialty Show'} · Staff`);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Rename state
  const [editingName, setEditingName] = useState(false);
  const [newName, setNewName] = useState('');

  // Owners state
  const [ownerInput, setOwnerInput] = useState('');
  const [staffOptions, setStaffOptions] = useState<SpecialtyShowOwnerInfo[]>([]);

  // DJs state
  const [djInput, setDjInput] = useState('');
  const [djSuggestions, setDjSuggestions] = useState<string[]>([]);
  const [allDJNames, setAllDJNames] = useState<string[]>([]);
  const [showDJSuggestions, setShowDJSuggestions] = useState(false);
  const [djHistory, setDjHistory] = useState<string[]>([]);

  const loadShow = useCallback(async () => {
    if (!id) return;
    try {
      setLoading(true);
      setError(null);
      const data = await specialtyShowsAPI.get(parseInt(id));
      setShow(data);
    } catch (err) {
      const apiError = err as APIError;
      setError(
        typeof apiError.detail === 'string' ? apiError.detail : 'Failed to load specialty show'
      );
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadShow();
    autocompleteAPI.getDJNames().then(setAllDJNames).catch(() => {});
    specialtyShowsAPI.listStaffEmails().then(setStaffOptions).catch(() => {});
    if (id) {
      specialtyShowsAPI.getDjHistory(parseInt(id)).then(setDjHistory).catch(() => {});
    }
  }, [id, loadShow]);

  const showEphemeralSuccess = (msg: string) => {
    setSuccessMessage(msg);
    setTimeout(() => setSuccessMessage(null), 3000);
  };

  const runMutation = async (
    action: () => Promise<unknown>,
    successMessage: string,
    errorFallback: string,
    onSuccess?: () => void
  ) => {
    setSaving(true);
    setFormError(null);
    try {
      await action();
      onSuccess?.();
      showEphemeralSuccess(successMessage);
      await loadShow();
    } catch (err) {
      const apiError = err as APIError;
      setFormError(typeof apiError.detail === 'string' ? apiError.detail : errorFallback);
    } finally {
      setSaving(false);
    }
  };

  const handleRename = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!show || !newName.trim()) return;
    await runMutation(
      () => specialtyShowsAPI.update(show.id, { name: newName.trim() }),
      'Show renamed.',
      'Failed to rename show',
      () => setEditingName(false)
    );
  };

  const handleAddOwner = async (rawEmail: string) => {
    if (!show) return;
    const email = extractPersonEmail(rawEmail);
    if (!email) return;
    if (show.owner_emails.includes(email)) {
      setFormError('That email is already an owner.');
      return;
    }
    await runMutation(
      () => specialtyShowsAPI.update(show.id, { owner_emails: [...show.owner_emails, email] }),
      'Owner added.',
      'Failed to add owner',
      () => setOwnerInput('')
    );
  };

  const handleRemoveOwner = async (email: string) => {
    if (!show) return;
    await runMutation(
      () =>
        specialtyShowsAPI.update(show.id, {
          owner_emails: show.owner_emails.filter((e) => e !== email),
        }),
      'Owner removed.',
      'Failed to remove owner'
    );
  };

  const handleDJInputChange = (value: string) => {
    setDjInput(value);
    if (value.trim()) {
      const filtered = allDJNames.filter((n) => n.toLowerCase().includes(value.toLowerCase()));
      setDjSuggestions(filtered);
      setShowDJSuggestions(filtered.length > 0);
    } else {
      setDjSuggestions([]);
      setShowDJSuggestions(false);
    }
  };

  const handleAddDJ = async (name?: string) => {
    if (!show) return;
    const djName = (name ?? djInput).trim();
    if (!djName) return;
    if (show.dj_names.includes(djName)) {
      setFormError('That DJ is already in this show.');
      return;
    }
    setShowDJSuggestions(false);
    setDjInput('');
    await runMutation(
      () => specialtyShowsAPI.update(show.id, { dj_names: [...show.dj_names, djName] }),
      'DJ added.',
      'Failed to add DJ'
    );
  };

  const handleRemoveDJ = async (djName: string) => {
    if (!show) return;
    await runMutation(
      () =>
        specialtyShowsAPI.update(show.id, {
          dj_names: show.dj_names.filter((n) => n !== djName),
        }),
      'DJ removed.',
      'Failed to remove DJ'
    );
  };

  const isOwner = show && user?.email
    ? show.owner_emails.includes(user.email)
    : false;

  const canEdit = isOwner || user?.role === 'promotions';

  const suggestedHosts = show ? djHistory.filter((name) => !show.dj_names.includes(name)) : [];

  if (loading) return <div className="loading">Loading...</div>;

  if (error || !show) {
    return (
      <div className="error">
        <p>Error: {error || 'Specialty show not found'}</p>
        <button onClick={() => navigate('/staff/specialty-shows')} className="btn-secondary">
          Back
        </button>
      </div>
    );
  }

  return (
    <div className="show-detail">
      <div className="page-header">
        <button onClick={() => navigate('/staff/specialty-shows')} className="btn-secondary">
          ← Back to Specialty Shows
        </button>
        <h2>
          {canEdit && editingName ? (
            <form onSubmit={handleRename} style={{ display: 'inline-flex', gap: '0.5rem', alignItems: 'center' }}>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="input-text"
                disabled={saving}
                autoFocus
              />
              <button type="submit" className="btn-small btn-primary" disabled={saving || !newName.trim()}>
                {saving ? 'Saving…' : 'Save'}
              </button>
              <button type="button" className="btn-small btn-secondary" onClick={() => setEditingName(false)} disabled={saving}>
                Cancel
              </button>
            </form>
          ) : (
            <>
              {show.name}{' '}
              {canEdit && (
                <button
                  className="btn-small btn-primary"
                  onClick={() => { setNewName(show.name); setEditingName(true); setFormError(null); }}
                  style={{ fontSize: '0.75rem', verticalAlign: 'middle' }}
                >
                  Rename
                </button>
              )}
            </>
          )}
        </h2>
      </div>

      {!canEdit && (
        <p className="field-hint">You're viewing this specialty show. Only its owners or promotions staff can make changes.</p>
      )}

      {successMessage && <div className="success-message">{successMessage}</div>}
      {formError && <div className="error-message">{formError}</div>}

      <div className="show-detail-content">
        {/* Owners section */}
        <div className="show-info-section">
          <h3>Owners</h3>
          <p className="field-hint">
            Owners can rename this show and manage its owners and DJs.
          </p>
          <ul className="item-list">
            {show.owner_details.map(({ email, name }) => (
              <li key={email} className="item-list-row">
                <span>{name ? `${name} (${email})` : email}</span>
                {canEdit && (
                  <button
                    className="btn-small btn-danger"
                    onClick={() => handleRemoveOwner(email)}
                    disabled={saving}
                  >
                    Remove
                  </button>
                )}
              </li>
            ))}
          </ul>
          {canEdit && (
            <div className="add-item-form">
              <PersonAutocomplete
                value={ownerInput}
                onChange={setOwnerInput}
                onSubmit={handleAddOwner}
                options={staffOptions}
                placeholder="Staff name or email address"
                disabled={saving}
              />
              <button
                className="btn-small btn-primary"
                onClick={() => handleAddOwner(ownerInput)}
                disabled={saving || !ownerInput.trim()}
              >
                Add Owner
              </button>
            </div>
          )}
        </div>

        {/* DJs section */}
        <div className="show-info-section">
          <h3>DJs</h3>
          <p className="field-hint">
            DJs listed here can reserve on-air pass pairs for this specialty show.
          </p>
          <ul className="item-list">
            {show.dj_names.map((name) => (
              <li key={name} className="item-list-row">
                <span>{name}</span>
                {canEdit && (
                  <button
                    className="btn-small btn-danger"
                    onClick={() => handleRemoveDJ(name)}
                    disabled={saving}
                  >
                    Remove
                  </button>
                )}
              </li>
            ))}
            {show.dj_names.length === 0 && (
              <li className="item-list-empty">No DJs yet.</li>
            )}
          </ul>
          {canEdit && suggestedHosts.length > 0 && (
            <div className="field-hint" style={{ marginBottom: '0.5rem' }}>
              Hosted this show recently:{' '}
              {suggestedHosts.map((name) => (
                <button
                  key={name}
                  type="button"
                  className="btn-small"
                  style={{ marginRight: '0.25rem', marginBottom: '0.25rem' }}
                  onClick={() => handleAddDJ(name)}
                  disabled={saving}
                >
                  + {name}
                </button>
              ))}
            </div>
          )}
          {canEdit && (
            <div className="add-item-form">
              <div className="autocomplete-wrapper">
                <input
                  type="text"
                  value={djInput}
                  onChange={(e) => handleDJInputChange(e.target.value)}
                  onFocus={() => { if (djInput.trim()) setShowDJSuggestions(true); }}
                  onBlur={() => setTimeout(() => setShowDJSuggestions(false), 200)}
                  placeholder="DJ name"
                  className="input-text"
                  disabled={saving}
                  autoComplete="off"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') { e.preventDefault(); handleAddDJ(); }
                    else if (e.key === 'Escape') { setShowDJSuggestions(false); }
                    else if (e.key === 'Tab' && djSuggestions.length === 1) {
                      e.preventDefault();
                      setDjInput(djSuggestions[0]);
                      setShowDJSuggestions(false);
                    }
                  }}
                />
                {showDJSuggestions && djSuggestions.length > 0 && (
                  <ul className="autocomplete-list">
                    {djSuggestions.map((name) => (
                      <li
                        key={name}
                        onMouseDown={() => handleAddDJ(name)}
                        className="autocomplete-item"
                      >
                        {name}
                      </li>
                    ))}
                    {djSuggestions.length === 1 && (
                      <li className="autocomplete-hint">Press Tab to complete</li>
                    )}
                  </ul>
                )}
              </div>
              <button
                className="btn-small btn-primary"
                onClick={() => handleAddDJ()}
                disabled={saving || !djInput.trim()}
              >
                Add DJ
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SpecialtyShowDetail;
