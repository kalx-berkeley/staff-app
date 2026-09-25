import { useState } from 'react';
import type { AlternateEntry, AlternateJoinRequest } from '../../types';

interface AlternateQueueListProps {
  entries: AlternateEntry[];
  myEntryId?: number | null;
  /** Rendered inside the current user's own card (edit/leave actions). */
  renderMyActions?: (entry: AlternateEntry) => React.ReactNode;
  /** Promotions only: remove someone from the queue. */
  onRemove?: (entry: AlternateEntry) => void;
  removingId?: number | null;
}

/**
 * The alternate queue, shown under a show's staff-pass claims: a divider,
 * then amber cards labeled "Alternate #N" in queue order.
 */
export const AlternateQueueList = ({
  entries,
  myEntryId = null,
  renderMyActions,
  onRemove,
  removingId = null,
}: AlternateQueueListProps) => {
  if (entries.length === 0) return null;
  return (
    <div className="alternate-queue">
      <div className="alternate-divider" role="separator">
        <span>Alternates ({entries.length})</span>
      </div>
      <div className="passes-list">
        {entries.map((entry) => {
          const isMine = entry.id === myEntryId;
          return (
            <div
              key={entry.id}
              className={`pass-card alternate-card${isMine ? ' alternate-card--mine' : ''}`}
            >
              <div className="pass-details">
                <p className="alternate-label">
                  Alternate #{entry.position}
                  {isMine && <span className="alternate-you"> (you)</span>}
                </p>
                <p><strong>Name:</strong> {entry.staff_name ?? '(name not recorded)'}</p>
                {entry.has_guest && (
                  <p className="pass-guest-note">
                    +1 guest requested{entry.guest_name ? `: ${entry.guest_name}` : ''}
                    {entry.only_attend_with_guest ? ' (only attending with guest)' : ''}
                  </p>
                )}
                {isMine && renderMyActions?.(entry)}
                {onRemove && (
                  <button
                    onClick={() => onRemove(entry)}
                    className="btn-small btn-danger"
                    disabled={removingId === entry.id}
                  >
                    {removingId === entry.id ? 'Removing…' : 'Remove'}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

interface AlternateGuestFormProps {
  idPrefix: string;
  requireGuestName: boolean;
  initial?: AlternateJoinRequest;
  submitLabel: string;
  busy: boolean;
  onSubmit: (data: AlternateJoinRequest) => void;
  onCancel: () => void;
}

/**
 * Join-as-alternate / edit-alternate form. Mirrors the staff pass claim form's
 * +1 guest options.
 */
export const AlternateGuestForm = ({
  idPrefix,
  requireGuestName,
  initial,
  submitLabel,
  busy,
  onSubmit,
  onCancel,
}: AlternateGuestFormProps) => {
  const [hasGuest, setHasGuest] = useState(initial?.has_guest ?? false);
  const [guestName, setGuestName] = useState(initial?.guest_name ?? '');
  const [onlyWithGuest, setOnlyWithGuest] = useState(initial?.only_attend_with_guest ?? false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = () => {
    if (hasGuest && requireGuestName && !guestName.trim()) {
      setError('Guest name is required for this venue');
      return;
    }
    setError(null);
    onSubmit({
      has_guest: hasGuest,
      guest_name: hasGuest ? guestName.trim() || null : null,
      only_attend_with_guest: hasGuest ? onlyWithGuest : false,
    });
  };

  return (
    <div className="guest-claim-form">
      <fieldset className="form-group radio-group">
        <legend>I'm waiting for:</legend>
        <label className="radio-label">
          <input
            type="radio"
            name={`${idPrefix}-pass-type`}
            checked={!hasGuest}
            onChange={() => setHasGuest(false)}
            disabled={busy}
          />
          {' '}A pass for myself
        </label>
        <label className="radio-label">
          <input
            type="radio"
            name={`${idPrefix}-pass-type`}
            checked={hasGuest}
            onChange={() => setHasGuest(true)}
            disabled={busy}
          />
          {' '}A pass for me and a guest
        </label>
      </fieldset>
      {hasGuest && (
        <>
          <p className="field-hint">
            Staff always come before +1 guests, so your guest only gets a pass if nobody else
            is waiting when yours opens up.
          </p>
          {requireGuestName && (
            <div className="form-group">
              <label htmlFor={`${idPrefix}-guest-name`}>Guest name (required by this venue):</label>
              <input
                id={`${idPrefix}-guest-name`}
                type="text"
                value={guestName}
                onChange={(e) => setGuestName(e.target.value)}
                placeholder="Guest full name"
                className="input-text"
                disabled={busy}
              />
            </div>
          )}
          <fieldset className="form-group radio-group">
            <legend>If there isn't a pass for my guest:</legend>
            <label className="radio-label">
              <input
                type="radio"
                name={`${idPrefix}-only-with-guest`}
                checked={!onlyWithGuest}
                onChange={() => setOnlyWithGuest(false)}
                disabled={busy}
              />
              {' '}I'll still attend without them
            </label>
            <label className="radio-label">
              <input
                type="radio"
                name={`${idPrefix}-only-with-guest`}
                checked={onlyWithGuest}
                onChange={() => setOnlyWithGuest(true)}
                disabled={busy}
              />
              {' '}Skip me until there's a pass for both of us
            </label>
          </fieldset>
        </>
      )}
      {error && <p className="field-error">{error}</p>}
      <div className="form-actions">
        <button onClick={handleSubmit} className="btn-small btn-primary" disabled={busy}>
          {busy ? 'Saving…' : submitLabel}
        </button>
        <button onClick={onCancel} className="btn-small btn-secondary" disabled={busy}>
          Cancel
        </button>
      </div>
    </div>
  );
};
