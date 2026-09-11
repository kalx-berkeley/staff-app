import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { specialtyShowsAPI, autocompleteAPI } from '../../services/api';
import { useAuth } from '../../contexts/authHooks';
import type { SpecialtyShowResponse, APIError } from '../../types';

const SpecialtyShowDetail = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [show, setShow] = useState<SpecialtyShowResponse | null>(null);
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
    if (id) {
      specialtyShowsAPI.getDjHistory(parseInt(id)).then(setDjHistory).catch(() => {});
    }
  }, [id, loadShow]);

  const showEphemeralSuccess = (msg: string) => {
    setSuccessMessage(msg);
    setTimeout(() => setSuccessMessage(null), 3000);
  };

  const handleRename = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!show || !newName.trim()) return;
    setSaving(true);
    setFormError(null);
    try {
      await specialtyShowsAPI.update(show.id, { name: newName.trim() });
      setEditingName(false);
      showEphemeralSuccess('Show renamed.');
      await loadShow();
    } catch (err) {
      const apiError = err as APIError;
      setFormError(
        typeof apiError.detail === 'string' ? apiError.detail : 'Failed to rename show'
      );
    } finally {
      setSaving(false);
    }
  };

  const handleAddOwner = async () => {
    if (!show || !ownerInput.trim()) return;
    const email = ownerInput.trim().toLowerCase();
    if (show.owner_emails.includes(email)) {
      setFormError('That email is already an owner.');
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      await specialtyShowsAPI.update(show.id, {
        owner_emails: [...show.owner_emails, email],
      });
      setOwnerInput('');
      showEphemeralSuccess('Owner added.');
      await loadShow();
    } catch (err) {
      const apiError = err as APIError;
      setFormError(
        typeof apiError.detail === 'string' ? apiError.detail : 'Failed to add owner'
      );
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveOwner = async (email: string) => {
    if (!show) return;
    setSaving(true);
    setFormError(null);
    try {
      await specialtyShowsAPI.update(show.id, {
        owner_emails: show.owner_emails.filter((e) => e !== email),
      });
      showEphemeralSuccess('Owner removed.');
      await loadShow();
    } catch (err) {
      const apiError = err as APIError;
      setFormError(
        typeof apiError.detail === 'string' ? apiError.detail : 'Failed to remove owner'
      );
    } finally {
      setSaving(false);
    }
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
    setSaving(true);
    setFormError(null);
    setShowDJSuggestions(false);
    setDjInput('');
    try {
      await specialtyShowsAPI.update(show.id, {
        dj_names: [...show.dj_names, djName],
      });
      showEphemeralSuccess('DJ added.');
      await loadShow();
    } catch (err) {
      const apiError = err as APIError;
      setFormError(
        typeof apiError.detail === 'string' ? apiError.detail : 'Failed to add DJ'
      );
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveDJ = async (djName: string) => {
    if (!show) return;
    setSaving(true);
    setFormError(null);
    try {
      await specialtyShowsAPI.update(show.id, {
        dj_names: show.dj_names.filter((n) => n !== djName),
      });
      showEphemeralSuccess('DJ removed.');
      await loadShow();
    } catch (err) {
      const apiError = err as APIError;
      setFormError(
        typeof apiError.detail === 'string' ? apiError.detail : 'Failed to remove DJ'
      );
    } finally {
      setSaving(false);
    }
  };

  const isOwner = show && user?.email
    ? show.owner_emails.includes(user.email)
    : false;

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

  if (!isOwner && user?.role !== 'promotions') {
    return (
      <div className="error">
        <p>You are not an owner of this specialty show.</p>
        <button onClick={() => navigate('/staff/specialty-shows')} className="btn-secondary">
          Back
        </button>
      </div>
    );
  }

  return (
    <div className="show-detail">
      <div className="page-header">
        <button onClick={() => navigate('/staff/specialty-shows')} className="btn-back">
          ← Back to Specialty Shows
        </button>
        <h2>
          {editingName ? (
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
              <button type="button" className="btn-small" onClick={() => setEditingName(false)} disabled={saving}>
                Cancel
              </button>
            </form>
          ) : (
            <>
              {show.name}{' '}
              <button
                className="btn-small"
                onClick={() => { setNewName(show.name); setEditingName(true); setFormError(null); }}
                style={{ fontSize: '0.75rem', verticalAlign: 'middle' }}
              >
                Rename
              </button>
            </>
          )}
        </h2>
      </div>

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
            {show.owner_emails.map((email) => (
              <li key={email} className="item-list-row">
                <span>{email}</span>
                <button
                  className="btn-small btn-danger"
                  onClick={() => handleRemoveOwner(email)}
                  disabled={saving}
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
          <div className="add-item-form">
            <input
              type="email"
              value={ownerInput}
              onChange={(e) => setOwnerInput(e.target.value)}
              placeholder="Staff email address"
              className="input-text"
              disabled={saving}
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleAddOwner(); } }}
            />
            <button
              className="btn-small btn-primary"
              onClick={handleAddOwner}
              disabled={saving || !ownerInput.trim()}
            >
              Add Owner
            </button>
          </div>
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
                <button
                  className="btn-small btn-danger"
                  onClick={() => handleRemoveDJ(name)}
                  disabled={saving}
                >
                  Remove
                </button>
              </li>
            ))}
            {show.dj_names.length === 0 && (
              <li className="item-list-empty">No DJs yet.</li>
            )}
          </ul>
          {suggestedHosts.length > 0 && (
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
        </div>
      </div>
    </div>
  );
};

export default SpecialtyShowDetail;
