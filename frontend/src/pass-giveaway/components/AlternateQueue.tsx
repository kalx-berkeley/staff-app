import { useState } from 'react';
import type { AlternateEntry, AlternateJoinRequest, GuestFallback, WaitingGuest } from '../types';
import { waitingFallbackNote } from '../utils';
import GuestFallbackOptions from './GuestFallbackOptions';

interface AlternateQueueListProps {
  entries: AlternateEntry[];
  myEntryId?: number | null;
  /** Rendered inside the current user's own card (edit/leave actions). */
  renderMyActions?: (entry: AlternateEntry) => React.ReactNode;
  /** Rendered in every card, below the name and +1 details. */
  renderDetails?: (entry: AlternateEntry) => React.ReactNode;
  /** Promotions only: remove someone from the queue. */
  onRemove?: (entry: AlternateEntry) => void;
  removingId?: number | null;
  /** Leave out the divider, when the surrounding panel has its own heading. */
  hideDivider?: boolean;
}

/**
 * The alternate queue, shown under a show's staff-pass claims: a divider,
 * then amber cards labeled "Alternate #N" in queue order.
 */
export const AlternateQueueList = ({
  entries,
  myEntryId = null,
  renderMyActions,
  renderDetails,
  onRemove,
  removingId = null,
  hideDivider = false,
}: AlternateQueueListProps) => {
  if (entries.length === 0) return null;
  return (
    <div className="alternate-queue">
      {!hideDivider && (
        <div className="alternate-divider" role="separator">
          <span>Alternates ({entries.length})</span>
        </div>
      )}
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
                {entry.source === 'released_at_close' && (
                  <p className="pass-guest-note">
                    Pass released at close, because their guest didn't have one
                  </p>
                )}
                {entry.has_guest && (
                  <p className="pass-guest-note">
                    +1 guest requested{entry.guest_name ? `: ${entry.guest_name}` : ''}
                    {entry.guest_fallback === 'release' ? ' (only attending with guest)' : ''}
                    {entry.source !== 'released_at_close' && waitingFallbackNote(entry.guest_fallback)}
                  </p>
                )}
                {renderDetails?.(entry)}
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

interface WaitingGuestsListProps {
  guests: WaitingGuest[];
  heading?: string;
  /** Promotions only: remove a guest from the list. */
  onRemove?: (guest: WaitingGuest) => void;
  removingPassId?: number | null;
}

/** +1 guests waiting for a pass, shown below the staff alternates with their own numbers. */
export const WaitingGuestsList = ({
  guests,
  heading = 'Guests waiting for a pass',
  onRemove,
  removingPassId = null,
}: WaitingGuestsListProps) => {
  if (guests.length === 0) return null;
  return (
    <>
      <div className="alternate-divider">
        <span>{heading}</span>
      </div>
      <div className="passes-list">
        {guests.map((guest) => (
          <div
            key={guest.pass_id}
            className={`pass-card alternate-card${guest.is_mine ? ' alternate-card--mine' : ''}`}
          >
            <div className="pass-details">
              <p className="alternate-label">
                Guest #{guest.position}
                {guest.is_mine && <span className="alternate-you"> (your guest)</span>}
              </p>
              <p>
                {guest.guest_name
                  ? `${guest.guest_name} (guest of ${guest.host_name ?? 'staff'})`
                  : `Guest of ${guest.host_name ?? 'staff'}`}
              </p>
              {onRemove && (
                <button
                  onClick={() => onRemove(guest)}
                  className="btn-small btn-danger"
                  disabled={removingPassId === guest.pass_id}
                >
                  {removingPassId === guest.pass_id ? 'Removing…' : 'Remove'}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </>
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
  const [guestFallback, setGuestFallback] = useState<GuestFallback>(
    initial?.guest_fallback ?? 'attend_alone'
  );
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
      guest_fallback: hasGuest ? guestFallback : 'attend_alone',
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
          <GuestFallbackOptions
            name={`${idPrefix}-guest-fallback`}
            legend="If there isn't a pass for my guest:"
            value={guestFallback}
            onChange={setGuestFallback}
            disabled={busy}
            forAlternate
          />
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
