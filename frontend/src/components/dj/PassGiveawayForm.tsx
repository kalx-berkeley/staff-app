import { useState, useEffect, useRef } from 'react';
import { passesAPI, showsAPI, autocompleteAPI, venuePassesAPI } from '../../services/api';
import { Tooltip } from '../shared';
import type { PassResponse, GiveawayData, WinnerEligibility, APIError } from '../../types';

const DJ_NAME_KEY = 'kalx_dj_name';

interface PassGiveawayFormProps {
  pass: PassResponse;
  venueId: number;
  onSuccess: () => void;
  djName?: string;
  winFrequencyDays?: number | null;
  requiresEmail?: boolean;
}

const PassGiveawayForm = ({ pass, venueId, onSuccess, djName: propDjName, winFrequencyDays, requiresEmail }: PassGiveawayFormProps) => {
  const [formData, setFormData] = useState<GiveawayData>({
    recipient_name: '',
    recipient_phone: '',
    recipient_email: '',
    given_away_by_dj: propDjName ?? localStorage.getItem(DJ_NAME_KEY) ?? '',
  });
  const [djNames, setDjNames] = useState<string[]>([]);
  const [filteredDjNames, setFilteredDjNames] = useState<string[]>([]);
  const [showAutocomplete, setShowAutocomplete] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [winEligibility, setWinEligibility] = useState<WinnerEligibility | null>(null);
  const [overrideIneligible, setOverrideIneligible] = useState(false);
  const autocompleteRef = useRef<HTMLUListElement>(null);

  useEffect(() => {
    loadDJNames();
  }, []);

  useEffect(() => {
    if (propDjName !== undefined) {
      setFormData((prev) => ({ ...prev, given_away_by_dj: propDjName }));
    }
  }, [propDjName]);

  const loadDJNames = async () => {
    try {
      const names = await autocompleteAPI.getDJNames();
      setDjNames(names);
    } catch (err) {
      console.error('Failed to load DJ names:', err);
    }
  };

  const handleInputChange = (field: keyof GiveawayData, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));

    if (field === 'recipient_phone') {
      setWinEligibility(null);
      setOverrideIneligible(false);
    }

    if (field === 'given_away_by_dj') {
      if (value.trim()) {
        const filtered = djNames.filter((name) =>
          name.toLowerCase().includes(value.toLowerCase())
        );
        setFilteredDjNames(filtered);
        setShowAutocomplete(filtered.length > 0);
      } else {
        setShowAutocomplete(false);
      }
    }
  };

  const selectDJName = (name: string) => {
    setFormData((prev) => ({ ...prev, given_away_by_dj: name }));
    setShowAutocomplete(false);
  };

  const handleDJKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Tab' && filteredDjNames.length === 1) {
      e.preventDefault();
      selectDJName(filteredDjNames[0]);
    }
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

  const saveDJName = (name: string) => {
    if (name.trim()) {
      localStorage.setItem(DJ_NAME_KEY, name.trim());
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
    if (!formData.given_away_by_dj.trim()) {
      setError('DJ name is required');
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
      };
      await passesAPI.giveaway(pass.id, payload);
      saveDJName(formData.given_away_by_dj);
      onSuccess();
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

    if (!formData.given_away_by_dj.trim()) {
      setError('DJ name is required');
      return;
    }

    try {
      setLoading(true);
      await showsAPI.recordAttempt(pass.show_id, formData.given_away_by_dj);
      saveDJName(formData.given_away_by_dj);
      setSuccessMessage('No winner recorded.');
      setTimeout(() => setSuccessMessage(null), 2500);
      onSuccess();
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
          This venue limits winners to once every <strong>{winFrequencyDays} days</strong>. You
          don&apos;t need to do anything — the system will automatically check the caller&apos;s
          phone number against past winners when you enter it below.
        </p>
      )}

      {successMessage && <div className="success-message">{successMessage}</div>}
      {error && <div className="error-message">{error}</div>}

      <form onSubmit={handleGiveaway}>
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
            <Tooltip text="The phone number is checked against this venue's win history. If this caller won recently, a warning will appear and you may need to override." />
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
              <em>{winEligibility.last_win_show}</em> (show date: {winEligibility.last_win_date}),
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

        <div className="form-group autocomplete-wrapper">
          <label htmlFor="given_away_by_dj">DJ Name *</label>
          <input
            type="text"
            id="given_away_by_dj"
            value={formData.given_away_by_dj}
            onChange={(e) => handleInputChange('given_away_by_dj', e.target.value)}
            onKeyDown={handleDJKeyDown}
            onFocus={() => {
              if (formData.given_away_by_dj.trim() && filteredDjNames.length > 0) {
                setShowAutocomplete(true);
              }
            }}
            onBlur={() => setTimeout(() => setShowAutocomplete(false), 200)}
            disabled={loading}
            placeholder="Enter DJ name"
            autoComplete="off"
          />
          {showAutocomplete && (
            <ul className="autocomplete-list" ref={autocompleteRef}>
              {filteredDjNames.map((name) => (
                <li
                  key={name}
                  onMouseDown={() => selectDJName(name)}
                  className="autocomplete-item"
                >
                  {name}
                </li>
              ))}
              {filteredDjNames.length === 1 && (
                <li className="autocomplete-hint">Press Tab to complete</li>
              )}
            </ul>
          )}
        </div>

        <div className="form-actions">
          <button
            type="submit"
            className="btn-primary"
            disabled={loading || isSubmitBlocked}
          >
            {loading ? 'Saving...' : 'Give Away'}
          </button>
          <button
            type="button"
            className="btn-secondary"
            onClick={handleNoWinner}
            disabled={loading}
            title="Record that you attempted the giveaway but no eligible caller won. This logs the attempt without awarding the pass."
          >
            Tried
          </button>
        </div>
      </form>
    </div>
  );
};

export default PassGiveawayForm;
