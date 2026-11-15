import { useState, useEffect, useCallback } from 'react';
import { Navigate, useParams, useNavigate } from 'react-router-dom';
import { specialtyShowsAPI } from '../api';
import { useAuth } from '../../common/contexts/authHooks';
import { usePageTitle } from '../../common/hooks/usePageTitle';
import { IdentityPicker, PersonAutocomplete, extractPersonEmail } from '../components';
import { SPECIALTY_SHOW_KINDS, specialtyShowPath } from '../utils';
import type { Identity, SpecialtyShowCategory, SpecialtyShowResponse, SpecialtyShowOwnerInfo } from '../types';
import type { APIError } from '../../common/types';

interface SpecialtyShowDetailProps {
  /** Which kind of show this page's URL is for. */
  category?: SpecialtyShowCategory;
}

/**
 * One Specialty Music Show or Talk & Info Show. A music show lists its DJs, a
 * talk show its staff members. A show opened under the other kind's URL is
 * redirected to its own.
 */
const SpecialtyShowDetail = ({ category = 'music' }: SpecialtyShowDetailProps) => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const kind = SPECIALTY_SHOW_KINDS[category];

  const [show, setShow] = useState<SpecialtyShowResponse | null>(null);
  usePageTitle(`${show?.name ?? kind.label} · Staff`);
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

  // Spinitron shows state
  const [spinitronInput, setSpinitronInput] = useState('');

  // Staff members state (talk shows)
  const [memberInput, setMemberInput] = useState('');

  // DJs state (music shows): the persona picked to add, and the personas
  // that can be added (current staff members')
  const [djPick, setDjPick] = useState<Identity | null>(null);
  const [djOptions, setDjOptions] = useState<Identity[]>([]);
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
        typeof apiError.detail === 'string' ? apiError.detail : `Failed to load ${kind.label}`
      );
    } finally {
      setLoading(false);
    }
  }, [id, kind.label]);

  useEffect(() => {
    loadShow();
    specialtyShowsAPI.listStaffEmails().then(setStaffOptions).catch(() => {});
    if (category === 'music') {
      if (id) {
        specialtyShowsAPI.getDjOptions(parseInt(id)).then(setDjOptions).catch(() => {});
        specialtyShowsAPI.getDjHistory(parseInt(id)).then(setDjHistory).catch(() => {});
      }
    }
  }, [id, loadShow, category]);

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

  const handleAddSpinitron = async () => {
    if (!show || !spinitronInput.trim()) return;
    await runMutation(
      () =>
        specialtyShowsAPI.update(show.id, {
          spinitron_urls: [...show.spinitron_shows.map((s) => s.url), spinitronInput.trim()],
        }),
      'Spinitron show added.',
      'Failed to add Spinitron show',
      () => setSpinitronInput('')
    );
  };

  const handleRemoveSpinitron = async (spinitronId: number) => {
    if (!show) return;
    await runMutation(
      () =>
        specialtyShowsAPI.update(show.id, {
          spinitron_urls: show.spinitron_shows.filter((s) => s.id !== spinitronId).map((s) => s.url),
        }),
      'Spinitron show removed.',
      'Failed to remove Spinitron show'
    );
  };

  const handleAddMember = async (rawEmail: string) => {
    if (!show) return;
    const email = extractPersonEmail(rawEmail);
    if (!email) return;
    if (show.staff_member_emails.includes(email)) {
      setFormError('That person is already on this show.');
      return;
    }
    await runMutation(
      () =>
        specialtyShowsAPI.update(show.id, {
          staff_member_emails: [...show.staff_member_emails, email],
        }),
      'Staff member added.',
      'Failed to add staff member',
      () => setMemberInput('')
    );
  };

  const handleRemoveMember = async (email: string) => {
    if (!show) return;
    await runMutation(
      () =>
        specialtyShowsAPI.update(show.id, {
          staff_member_emails: show.staff_member_emails.filter((e) => e !== email),
        }),
      'Staff member removed.',
      'Failed to remove staff member'
    );
  };

  // The show's DJs by persona; an old entry without one can only be removed
  const djPersonaIds = show
    ? show.djs.flatMap((d) => (d.persona_id !== null ? [d.persona_id] : []))
    : [];

  const handleAddDJ = async (persona: Identity | null = djPick) => {
    if (!show || persona?.persona_id == null) return;
    if (djPersonaIds.includes(persona.persona_id)) {
      setFormError('That DJ is already in this show.');
      return;
    }
    setDjPick(null);
    await runMutation(
      () =>
        specialtyShowsAPI.update(show.id, {
          dj_persona_ids: [...djPersonaIds, persona.persona_id!],
        }),
      'DJ added.',
      'Failed to add DJ'
    );
  };

  const handleRemoveDJ = async (index: number) => {
    if (!show) return;
    const removed = show.djs[index].persona_id;
    await runMutation(
      () =>
        specialtyShowsAPI.update(show.id, {
          dj_persona_ids: djPersonaIds.filter((pid) => pid !== removed),
        }),
      'DJ removed.',
      'Failed to remove DJ'
    );
  };

  const isOwner = show && user?.email
    ? show.owner_emails.includes(user.email)
    : false;

  const canEdit = isOwner || user?.role === 'promotions';

  // Recent hosts of the show's Spinitron show who can be added (by name)
  const suggestedHosts = djOptions.filter(
    (o) =>
      o.persona_id !== null &&
      !djPersonaIds.includes(o.persona_id) &&
      djHistory.some((name) => name.toLowerCase() === o.name.toLowerCase())
  );

  if (loading) return <div className="loading">Loading...</div>;

  if (error || !show) {
    return (
      <div className="error">
        <p>Error: {error || `${kind.label} not found`}</p>
        <button onClick={() => navigate(kind.path)} className="btn-secondary">
          Back
        </button>
      </div>
    );
  }

  if (show.category !== category) {
    return <Navigate to={specialtyShowPath(show)} replace />;
  }

  return (
    <div className="show-detail">
      <div className="page-header">
        <button onClick={() => navigate(kind.path)} className="btn-secondary">
          ← Back to {kind.plural}
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
        <p className="field-hint">You're viewing this {kind.label}. Only its owners or promotions staff can make changes.</p>
      )}
      {show.retired && (
        <p className="info-message">
          This show is retired: it can no longer get passes. Un-retire it from the {kind.plural} list.
        </p>
      )}

      {successMessage && <div className="success-message">{successMessage}</div>}
      {formError && <div className="error-message">{formError}</div>}

      <div className="specialty-show-sections">
        {/* Spinitron section */}
        <section className="info-section">
          <h3>Spinitron</h3>
          <p className="field-hint">
            The show's page in Spinitron, so the Staff Directory can tell this {kind.label} apart
            from regular DJ shifts. Paste a link to the show or to one of its playlists. If the show
            has moved to a new Spinitron show over the years, add each one.
          </p>
          {show.spinitron_shows.length === 0 && (
            <p className="field-warning">
              Add this show's Spinitron link{canEdit ? ' before making other changes' : ''}.
            </p>
          )}
          <ul className="item-list">
            {show.spinitron_shows.map((s) => (
              <li key={s.id} className="item-list-row">
                <a href={s.url} target="_blank" rel="noreferrer">
                  {s.title || `Show ${s.id}`}
                </a>
                {canEdit && show.spinitron_shows.length > 1 && (
                  <button
                    className="btn-small btn-danger"
                    onClick={() => handleRemoveSpinitron(s.id)}
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
              <input
                type="url"
                value={spinitronInput}
                onChange={(e) => setSpinitronInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') { e.preventDefault(); handleAddSpinitron(); }
                }}
                placeholder="https://spinitron.com/KALX/show/…"
                aria-label="Spinitron show or playlist link"
                className="input-text"
                disabled={saving}
              />
              <button
                className="btn-small btn-primary"
                onClick={handleAddSpinitron}
                disabled={saving || !spinitronInput.trim()}
              >
                Add Spinitron Link
              </button>
            </div>
          )}
        </section>

        {/* Owners section */}
        <section className="info-section">
          <h3>Owners</h3>
          <p className="field-hint">
            Owners can rename this show and manage its owners and{' '}
            {category === 'talk' ? 'staff members' : 'DJs'}.
          </p>
          <ul className="item-list">
            {show.owner_details.map(({ email, name }) => (
              <li key={email} className="item-list-row">
                <span><a href={`mailto:${email}`}>{name || email}</a></span>
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
        </section>

        {category === 'talk' && (
          <section className="info-section">
            <h3>Staff Members</h3>
            <p className="field-hint">
              Staff members listed here can reserve on-air pass pairs for this Talk &amp; Info Show.
              They don't need to be DJs.
            </p>
            <ul className="item-list">
              {show.staff_member_details.map(({ email, name }) => (
                <li key={email} className="item-list-row">
                  <span><a href={`mailto:${email}`}>{name || email}</a></span>
                  {canEdit && (
                    <button
                      className="btn-small btn-danger"
                      onClick={() => handleRemoveMember(email)}
                      disabled={saving}
                    >
                      Remove
                    </button>
                  )}
                </li>
              ))}
              {show.staff_member_details.length === 0 && (
                <li className="item-list-empty">No staff members yet.</li>
              )}
            </ul>
            {canEdit && (
              <div className="add-item-form">
                <PersonAutocomplete
                  value={memberInput}
                  onChange={setMemberInput}
                  onSubmit={handleAddMember}
                  options={staffOptions}
                  placeholder="Staff name or email address"
                  disabled={saving}
                />
                <button
                  className="btn-small btn-primary"
                  onClick={() => handleAddMember(memberInput)}
                  disabled={saving || !memberInput.trim()}
                >
                  Add Staff Member
                </button>
              </div>
            )}
          </section>
        )}

        {/* DJs section */}
        {category === 'music' && (
          <section className="info-section">
            <h3>DJs</h3>
            <p className="field-hint">
              DJs listed here can reserve on-air pass pairs for this Specialty Music Show.
            </p>
            <ul className="item-list">
              {show.djs.map((dj, index) => (
                <li key={dj.persona_id ?? `name:${dj.name}`} className="item-list-row">
                  <span>
                    {dj.name}
                    {dj.persona_id === null && (
                      <span className="field-hint"> (not linked to a Spinitron persona yet)</span>
                    )}
                  </span>
                  {canEdit && dj.persona_id !== null && (
                    <button
                      className="btn-small btn-danger"
                      onClick={() => handleRemoveDJ(index)}
                      disabled={saving}
                    >
                      Remove
                    </button>
                  )}
                </li>
              ))}
              {show.djs.length === 0 && (
                <li className="item-list-empty">No DJs yet.</li>
              )}
            </ul>
            {canEdit && suggestedHosts.length > 0 && (
              <div className="field-hint" style={{ marginBottom: '0.5rem' }}>
                Hosted this show recently:{' '}
                {suggestedHosts.map((host) => (
                  <button
                    key={host.persona_id}
                    type="button"
                    className="btn-small"
                    style={{ marginRight: '0.25rem', marginBottom: '0.25rem' }}
                    onClick={() => handleAddDJ(host)}
                    disabled={saving}
                  >
                    + {host.name}
                  </button>
                ))}
              </div>
            )}
            {canEdit && (
              <div className="add-item-form">
                <IdentityPicker
                  options={djOptions.filter(
                    (o) => o.persona_id !== null && !djPersonaIds.includes(o.persona_id)
                  )}
                  value={djPick}
                  onChange={setDjPick}
                  disabled={saving}
                  placeholder="DJ name"
                  aria-label="DJ to add"
                />
                <button
                  className="btn-small btn-primary"
                  onClick={() => handleAddDJ()}
                  disabled={saving || !djPick}
                >
                  Add DJ
                </button>
              </div>
            )}
          </section>
        )}
      </div>
    </div>
  );
};

/** One Talk & Info Show, at `/staff/talk-shows/:id`. */
export const TalkShowDetail = () => <SpecialtyShowDetail category="talk" />;

export default SpecialtyShowDetail;
