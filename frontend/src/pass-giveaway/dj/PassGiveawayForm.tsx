import { useState } from 'react';
import { passesAPI, showsAPI, venuePassesAPI } from '../api';
import { Tooltip } from '../components';
import type { PassResponse, GiveawayData, WinnerEligibility } from '../types';
import type { APIError } from '../../common/types';
import { joinNames } from '../utils';
import PhoneInput from '../../common/components/PhoneInput';
import { US_PHONE_DIGITS } from '../../common/utils';

interface PassGiveawayFormProps {
  pass: PassResponse;
  venueId: number;
  /** Called after Give Away (`'given_away'`) or Tried (`'tried'`) is recorded. */
  onSuccess: (outcome: GiveawayOutcome) => void;
  winFrequencyDays?: number | null;
  // The other venues that share this venue's win frequency limit
  winFrequencySharedWith?: string[];
  requiresEmail?: boolean;
  /**
   * View only, for someone who can't record a giveaway (away from the DJ
   * studio): the form shows as it does on air, but every field and button is
   * disabled.
   */
  viewOnly?: boolean;
  /** The giveaway page visit, sent with the giveaway or attempt for KALX Staff Analytics. */
  visitId?: string | null;
}

export type GiveawayOutcome = 'given_away' | 'tried';

type WinnerFields = Omit<GiveawayData, 'visit_id'>;

// Who the giveaway or attempt is credited to is up to the server: whoever
// the Spinitron schedule has on air (see dj/onAirContext.tsx).
const PassGiveawayForm = ({ pass, venueId, onSuccess, winFrequencyDays, winFrequencySharedWith = [], requiresEmail, viewOnly, visitId }: PassGiveawayFormProps) => {
  const [formData, setFormData] = useState<WinnerFields>({
    recipient_name: '',
    recipient_phone: '',
    recipient_email: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [winEligibility, setWinEligibility] = useState<WinnerEligibility | null>(null);
  const [overrideIneligible, setOverrideIneligible] = useState(false);

  const handleInputChange = (field: keyof WinnerFields, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));

    if (field === 'recipient_phone') {
      setWinEligibility(null);
      setOverrideIneligible(false);
    }
  };

  const handlePhoneBlur = async () => {
    const phone = formData.recipient_phone;
    if (phone.length !== US_PHONE_DIGITS || !venueId) return;
    try {
      const result = await venuePassesAPI.checkWinner(venueId, phone, pass.show_id);
      setWinEligibility(result);
    } catch {
      // Silently ignore check failures — don't block the DJ
    }
  };

  const isSubmitBlocked = winEligibility?.eligible === false && !overrideIneligible;

  const handleGiveaway = async (e: React.FormEvent) => {
    e.preventDefault();
    // The disabled fieldset stops this in browsers; this guards anything else
    if (viewOnly) return;
    setError(null);

    if (!formData.recipient_name.trim()) {
      setError('Winner name is required');
      return;
    }
    if (!formData.recipient_phone) {
      setError('Winner phone is required');
      return;
    }
    if (formData.recipient_phone.length !== US_PHONE_DIGITS) {
      setError('Phone number must have 10 digits');
      return;
    }
    if (requiresEmail && !formData.recipient_email?.trim()) {
      setError('Winner email address is required by this venue');
      return;
    }
    if (isSubmitBlocked) {
      setError('Winner is ineligible. Check the override box to proceed.');
      return;
    }

    try {
      setLoading(true);
      const payload: GiveawayData = {
        ...formData,
        recipient_email: formData.recipient_email?.trim() || null,
        ...(visitId ? { visit_id: visitId } : {}),
      };
      await passesAPI.giveaway(pass.id, payload);
      onSuccess('given_away');
    } catch (err) {
      const apiError = err as APIError;
      setError(
        typeof apiError.detail === 'string'
          ? apiError.detail
          : 'Failed to record giveaway'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleNoWinner = async () => {
    if (viewOnly) return;
    setError(null);

    try {
      setLoading(true);
      await showsAPI.recordAttempt(pass.show_id, visitId);
      onSuccess('tried');
    } catch (err) {
      const apiError = err as APIError;
      setError(
        typeof apiError.detail === 'string'
          ? apiError.detail
          : 'Failed to log attempt'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="pass-giveaway-form">
      {pass.preassigned_dj && (
        <div className="preassignment-notice">
          <p>
            <strong>Pre-assigned to:</strong> {pass.preassigned_dj}
            {pass.preassigned_date && ` on ${pass.preassigned_date}`}
          </p>
        </div>
      )}

      {winFrequencyDays && (
        <p className="win-frequency-notice">
          This venue limits winners to once every <strong>{winFrequencyDays} days</strong>
          {winFrequencySharedWith.length > 0 && <> (shared with {joinNames(winFrequencySharedWith)})</>}. You
          don&apos;t need to do anything — the system will automatically check the caller&apos;s
          phone number against past winners when you enter it below.
        </p>
      )}

      {error && <div className="error-message">{error}</div>}

      <form onSubmit={handleGiveaway}>
        <fieldset className="giveaway-view-only-fieldset" disabled={viewOnly}>
          <fieldset className="giveaway-winner-fieldset">
            <legend>Caller won</legend>
            <div className="form-group">
              <label htmlFor="recipient_name">Winner Name *</label>
              <input
                type="text"
                id="recipient_name"
                value={formData.recipient_name}
                onChange={(e) => handleInputChange('recipient_name', e.target.value)}
                disabled={loading}
                placeholder="Enter winner's name"
                autoComplete="off"
              />
            </div>

            <div className="form-group">
              <div className="label-with-help">
                <label htmlFor="recipient_phone">Winner Phone *</label>
                {winFrequencyDays ? (
                  <Tooltip text="The phone number is checked against the win history of this venue and any venues sharing its limit. If this caller won recently, a warning will appear and you may need to override." />
                ) : null}
              </div>
              <PhoneInput
                id="recipient_phone"
                value={formData.recipient_phone}
                onChange={(phone) => handleInputChange('recipient_phone', phone)}
                onBlur={handlePhoneBlur}
                disabled={loading}
                placeholder="Enter winner's phone number"
              />
              {winEligibility?.eligible === false && (
                <div className="win-ineligible-warning">
                  <strong>Warning:</strong> This caller already won passes to{' '}
                  <em>{winEligibility.last_win_show}</em>
                  {winEligibility.last_win_venue && <> at <strong>{winEligibility.last_win_venue}</strong></>}{' '}
                  (show date: {winEligibility.last_win_date}),
                  which is only {winEligibility.days_since} day{winEligibility.days_since !== 1 ? 's' : ''} before this show.
                  The venue requires at least {winEligibility.required_days} days between show dates.
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

            {requiresEmail && (
              <div className="form-group">
                <label htmlFor="recipient_email">Winner Email *</label>
                <p className="field-hint">
                  This venue requires the winner's email address for their guest list.
                </p>
                <input
                  type="email"
                  id="recipient_email"
                  value={formData.recipient_email ?? ''}
                  onChange={(e) => handleInputChange('recipient_email', e.target.value)}
                  disabled={loading}
                  placeholder="Enter winner's email address"
                  autoComplete="off"
                />
              </div>
            )}

            <div className="form-actions">
              <button
                type="submit"
                className="btn-primary"
                disabled={loading || isSubmitBlocked}
              >
                {loading ? 'Saving...' : 'Give Away'}
              </button>
            </div>
        </fieldset>

        <div className="giveaway-no-winner">
          <span className="giveaway-no-winner-label">No caller won?</span>
          <button
            type="button"
            className="btn-secondary"
            onClick={handleNoWinner}
            disabled={loading}
          >
            Tried
          </button>
          <span className="field-hint">Records the attempt. The pass stays available.</span>
        </div>
        </fieldset>
      </form>
    </div>
  );
};

export default PassGiveawayForm;
