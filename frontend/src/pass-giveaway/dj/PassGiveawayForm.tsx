import { useState } from 'react';
import { passesAPI, showsAPI, venuePassesAPI } from '../api';
import { Tooltip } from '../components';
import type { PassResponse, GiveawayData, WinnerEligibility } from '../types';
import type { APIError } from '../../common/types';
import { findRecentDjGiveaway, joinNames } from '../utils';
import { getPreviewGiveaways, recordPreviewGiveaway } from './previewGiveaways';

interface PassGiveawayFormProps {
  pass: PassResponse;
  venueId: number;
  /** Called after Give Away (`'given_away'`) or Tried (`'tried'`) is recorded. */
  onSuccess: (outcome: GiveawayOutcome) => void;
  /** The DJ name from the page's DJ Name box. Both Give Away and Tried need it. */
  djName: string;
  /** Called when Give Away or Tried is clicked without a DJ name, so the page can focus its DJ Name box. */
  onMissingDjName?: () => void;
  winFrequencyDays?: number | null;
  // The other venues that share this venue's win frequency limit
  winFrequencySharedWith?: string[];
  requiresEmail?: boolean;
  /**
   * Preview mode, for someone who can't really record a giveaway: the form
   * works as usual, checks included, but Give Away and Tried only pretend to
   * save (see previewGiveaways.ts) before calling onSuccess.
   */
  preview?: boolean;
  /** The giveaway page visit, sent with the giveaway or attempt for KALX Staff Analytics. */
  visitId?: string | null;
}

export type GiveawayOutcome = 'given_away' | 'tried';

type WinnerFields = Omit<GiveawayData, 'given_away_by_dj' | 'visit_id'>;

const PassGiveawayForm = ({ pass, venueId, onSuccess, djName, onMissingDjName, winFrequencyDays, winFrequencySharedWith = [], requiresEmail, preview, visitId }: PassGiveawayFormProps) => {
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

  /** Shows the missing DJ name error and returns false when the page's DJ Name box is empty. */
  const checkDjName = (): boolean => {
    if (djName.trim()) return true;
    setError('Enter your DJ name in the DJ Name box at the top of the page');
    onMissingDjName?.();
    return false;
  };

  const validatePhoneNumber = (phone: string): boolean => {
    const digitsOnly = phone.replace(/\D/g, '');
    return digitsOnly.length >= 10;
  };

  const handlePhoneBlur = async () => {
    const phone = formData.recipient_phone.trim();
    if (!phone || !validatePhoneNumber(phone) || !venueId) return;
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
    setError(null);

    if (!formData.recipient_name.trim()) {
      setError('Winner name is required');
      return;
    }
    if (!formData.recipient_phone.trim()) {
      setError('Winner phone is required');
      return;
    }
    if (!validatePhoneNumber(formData.recipient_phone)) {
      setError('Phone number must contain at least 10 digits');
      return;
    }
    if (requiresEmail && !formData.recipient_email?.trim()) {
      setError('Winner email address is required by this venue');
      return;
    }
    if (!checkDjName()) return;
    if (isSubmitBlocked) {
      setError('Winner is ineligible. Check the override box to proceed.');
      return;
    }

    if (preview) {
      // The same one-pair-per-shift refusal the backend gives
      const name = djName.trim();
      const showPreviews = getPreviewGiveaways().filter((g) => g.show_id === pass.show_id);
      if (findRecentDjGiveaway(showPreviews, name)) {
        setError(`DJ '${name}' has already given away a pair of passes for this show within the last 4 hours`);
        return;
      }
      recordPreviewGiveaway({
        show_id: pass.show_id,
        given_away_by_dj: name,
        recipient_name: formData.recipient_name.trim(),
      });
      onSuccess('given_away');
      return;
    }

    try {
      setLoading(true);
      const payload: GiveawayData = {
        ...formData,
        given_away_by_dj: djName.trim(),
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
    setError(null);

    if (!checkDjName()) return;

    if (preview) {
      onSuccess('tried');
      return;
    }

    try {
      setLoading(true);
      await showsAPI.recordAttempt(pass.show_id, djName.trim(), visitId);
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
            <input
              type="tel"
              id="recipient_phone"
              value={formData.recipient_phone}
              onChange={(e) => handleInputChange('recipient_phone', e.target.value)}
              onBlur={handlePhoneBlur}
              disabled={loading}
              placeholder="Enter winner's phone number"
              autoComplete="off"
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
      </form>
    </div>
  );
};

export default PassGiveawayForm;
