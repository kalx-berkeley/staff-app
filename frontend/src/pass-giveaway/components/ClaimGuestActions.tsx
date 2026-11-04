import { useState } from 'react';
import { passesAPI } from '../api';
import type { GuestFallback, PassResponse } from '../types';
import type { APIError } from '../../common/types';
import GuestFallbackOptions from './GuestFallbackOptions';

interface ClaimGuestActionsProps {
  pass: PassResponse;
  /** Free staff passes right now, which decides whether a new guest can be seated. */
  availableCount: number;
  requireGuestName: boolean;
  /** Adding a guest follows the same rules as claiming, so it can be turned off. */
  canAddGuest: boolean;
  /** Called after a change, with a message to show. */
  onChanged: (message: string) => Promise<void> | void;
}

type Mode = 'add' | 'rename' | 'remove' | null;

const errorMessage = (err: unknown, fallback: string): string => {
  const detail = (err as APIError).detail;
  return typeof detail === 'string' ? detail : fallback;
};

/** A staff member's own guest controls on their claimed pass: add, rename and remove. */
const ClaimGuestActions = ({
  pass,
  availableCount,
  requireGuestName,
  canAddGuest,
  onChanged,
}: ClaimGuestActionsProps) => {
  const hasGuest = pass.has_guest || pass.guest_waiting;
  const waitOnly = availableCount < 1;
  const [mode, setMode] = useState<Mode>(null);
  const [name, setName] = useState('');
  const [fallback, setFallback] = useState<GuestFallback>('attend_alone');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const open = (next: Mode) => {
    setMode(next);
    setError(null);
    setName(next === 'rename' ? pass.guest_name ?? '' : '');
    setFallback(waitOnly ? 'wait' : 'attend_alone');
  };

  const run = async (action: () => Promise<unknown>, success: string, failure: string) => {
    if (mode !== 'remove' && requireGuestName && !name.trim()) {
      setError('Guest name is required for this venue');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await action();
      setMode(null);
      await onChanged(success);
    } catch (err) {
      setError(errorMessage(err, failure));
    } finally {
      setBusy(false);
    }
  };

  const nameField = (requireGuestName || mode === 'rename') && (
    <div className="form-group">
      <label htmlFor={`guest-name-${pass.id}`}>
        Guest name{requireGuestName ? ' (required by this venue)' : ''}:
      </label>
      <input
        id={`guest-name-${pass.id}`}
        type="text"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Guest full name"
        className="input-text"
        disabled={busy}
      />
    </div>
  );

  const cancelButton = (
    <button onClick={() => setMode(null)} className="btn-small btn-secondary" disabled={busy}>
      Cancel
    </button>
  );

  if (mode === 'add') {
    return (
      <div className="guest-claim-form">
        <p className="guest-claim-info">
          A guest added now goes behind any guests already waiting for a pass.
        </p>
        {nameField}
        <GuestFallbackOptions
          name={`add-guest-fallback-${pass.id}`}
          legend="If my guest can't attend:"
          value={fallback}
          onChange={setFallback}
          disabled={busy}
          waitOnly={waitOnly}
        />
        {error && <p className="field-error">{error}</p>}
        <div className="form-actions">
          <button
            onClick={() =>
              run(
                () => passesAPI.addGuest(pass.id, { guest_name: name.trim() || null, guest_fallback: fallback }),
                'Your guest has been added.',
                'Failed to add your guest'
              )
            }
            className="btn-small btn-primary"
            disabled={busy}
          >
            {busy ? 'Adding…' : 'Add guest'}
          </button>
          {cancelButton}
        </div>
      </div>
    );
  }

  if (mode === 'rename') {
    return (
      <div className="guest-claim-form">
        {nameField}
        {error && <p className="field-error">{error}</p>}
        <div className="form-actions">
          <button
            onClick={() =>
              run(
                () => passesAPI.updateGuestName(pass.id, name.trim() || null),
                "Your guest's name has been updated.",
                "Failed to update your guest's name"
              )
            }
            className="btn-small btn-primary"
            disabled={busy}
          >
            {busy ? 'Saving…' : 'Save name'}
          </button>
          {cancelButton}
        </div>
      </div>
    );
  }

  if (mode === 'remove') {
    return (
      <div className="guest-claim-form">
        <p className="guest-claim-info">
          Remove {pass.guest_name || 'your guest'}? You'll keep your own pass. If you add a guest
          again, they'll go behind any guests already waiting for a pass.
        </p>
        {error && <p className="field-error">{error}</p>}
        <div className="form-actions">
          <button
            onClick={() =>
              run(
                () => passesAPI.removeGuest(pass.id),
                'Your guest has been removed.',
                'Failed to remove your guest'
              )
            }
            className="btn-small btn-danger"
            disabled={busy}
          >
            {busy ? 'Removing…' : 'Remove my guest'}
          </button>
          {cancelButton}
        </div>
      </div>
    );
  }

  if (!hasGuest) {
    return canAddGuest ? (
      <div className="claim-buttons guest-actions">
        <button onClick={() => open('add')} className="btn-small">
          Add a guest
        </button>
      </div>
    ) : null;
  }

  return (
    <div className="claim-buttons guest-actions">
      <button onClick={() => open('rename')} className="btn-small">
        Fix guest name
      </button>
      <button onClick={() => open('remove')} className="btn-small">
        Remove my guest
      </button>
    </div>
  );
};

export default ClaimGuestActions;
