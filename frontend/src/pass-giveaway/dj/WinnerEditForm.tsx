import { useEffect, useState } from 'react';
import { passesAPI, venuePassesAPI } from '../api';
import { formatPhone } from '../../common/utils';
import type { PassResponse, WinnerEligibility } from '../types';
import type { APIError } from '../../common/types';

interface WinnerEditFormProps {
  pass: PassResponse;
  venueId: number;
  djName: string;
  requiresEmail: boolean;
  onSaved: (updated: PassResponse) => void;
  onCancel: () => void;
}

const digits = (phone: string) => phone.replace(/\D/g, '');

const errorDetail = (err: unknown, fallback: string) => {
  const detail = (err as APIError).detail;
  return typeof detail === 'string' ? detail : fallback;
};

/**
 * Inline form for the on-air DJ to correct the winner they recorded (a typo in
 * the caller's name, phone or email). It loads the winner from the backend,
 * which only answers the DJ who gave the passes away, within 4 hours.
 */
const WinnerEditForm = ({
  pass,
  venueId,
  djName,
  requiresEmail,
  onSaved,
  onCancel,
}: WinnerEditFormProps) => {
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [originalPhone, setOriginalPhone] = useState('');
  const [hadEmail, setHadEmail] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [winEligibility, setWinEligibility] = useState<WinnerEligibility | null>(null);
  const [overrideIneligible, setOverrideIneligible] = useState(false);

  useEffect(() => {
    let cancelled = false;
    passesAPI
      .getWinnerForEdit(pass.id, djName.trim())
      .then((winner) => {
        if (cancelled) return;
        setName(winner.recipient_name ?? '');
        setPhone(winner.recipient_phone ? formatPhone(winner.recipient_phone) : '');
        setOriginalPhone(digits(winner.recipient_phone ?? ''));
        setEmail(winner.recipient_email ?? '');
        setHadEmail(!!winner.recipient_email);
        setLoaded(true);
      })
      .catch((err) => {
        if (!cancelled) setError(errorDetail(err, 'Failed to load the winner'));
      });
    return () => {
      cancelled = true;
    };
  }, [pass.id, djName]);

  const handlePhoneChange = (value: string) => {
    setPhone(value);
    setWinEligibility(null);
    setOverrideIneligible(false);
  };

  const handlePhoneBlur = async () => {
    const phoneDigits = digits(phone);
    if (phoneDigits.length < 10 || phoneDigits === originalPhone) return;
    try {
      setWinEligibility(
        await venuePassesAPI.checkWinner(venueId, phone.trim(), pass.show_id, pass.id)
      );
    } catch {
      // Don't block the DJ when the check fails; the backend still logs overrides.
    }
  };

  const isSaveBlocked = winEligibility?.eligible === false && !overrideIneligible;

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!name.trim()) {
      setError('Winner name is required');
      return;
    }
    if (digits(phone).length < 10) {
      setError('Phone number must contain at least 10 digits');
      return;
    }
    if (requiresEmail && !email.trim()) {
      setError('Winner email address is required by this venue');
      return;
    }
    if (isSaveBlocked) {
      setError('Winner is ineligible. Check the override box to proceed.');
      return;
    }
    try {
      setSaving(true);
      const updated = await passesAPI.updateWinner(pass.id, {
        recipient_name: name.trim(),
        recipient_phone: phone.trim(),
        recipient_email: email.trim() || null,
        given_away_by_dj: djName.trim(),
      });
      onSaved(updated);
    } catch (err) {
      setError(errorDetail(err, 'Failed to save the winner'));
      setSaving(false);
    }
  };

  const disabled = !loaded || saving;

  return (
    <form className="pass-giveaway-form winner-edit-form" onSubmit={handleSave}>
      {error && <div className="error-message">{error}</div>}
      {!loaded && !error && <p className="field-hint">Loading winner…</p>}

      <div className="form-group">
        <label htmlFor={`edit-recipient-name-${pass.id}`}>Winner Name *</label>
        <input
          type="text"
          id={`edit-recipient-name-${pass.id}`}
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={disabled}
          autoComplete="off"
        />
      </div>

      <div className="form-group">
        <label htmlFor={`edit-recipient-phone-${pass.id}`}>Winner Phone *</label>
        <input
          type="tel"
          id={`edit-recipient-phone-${pass.id}`}
          value={phone}
          onChange={(e) => handlePhoneChange(e.target.value)}
          onBlur={handlePhoneBlur}
          disabled={disabled}
          autoComplete="off"
        />
        {winEligibility?.eligible === false && (
          <div className="win-ineligible-warning">
            <strong>Warning:</strong> This caller already won passes to{' '}
            <em>{winEligibility.last_win_show}</em>
            {winEligibility.last_win_venue && <> at <strong>{winEligibility.last_win_venue}</strong></>}{' '}
            (show date: {winEligibility.last_win_date}),
            which is only {winEligibility.days_since} day
            {winEligibility.days_since !== 1 ? 's' : ''} before this show. The venue requires at
            least {winEligibility.required_days} days between show dates.
            <label className="override-label">
              <input
                type="checkbox"
                checked={overrideIneligible}
                onChange={(e) => setOverrideIneligible(e.target.checked)}
              />
              Override — proceed anyway and award these passes to this caller
            </label>
          </div>
        )}
      </div>

      {(requiresEmail || hadEmail) && (
        <div className="form-group">
          <label htmlFor={`edit-recipient-email-${pass.id}`}>
            Winner Email{requiresEmail ? ' *' : ''}
          </label>
          <input
            type="email"
            id={`edit-recipient-email-${pass.id}`}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={disabled}
            autoComplete="off"
          />
        </div>
      )}

      <div className="form-actions">
        <button type="submit" className="btn-primary" disabled={disabled || isSaveBlocked}>
          {saving ? 'Saving...' : 'Save'}
        </button>
        <button type="button" className="btn-secondary" onClick={onCancel} disabled={saving}>
          Cancel
        </button>
      </div>
    </form>
  );
};

export default WinnerEditForm;
