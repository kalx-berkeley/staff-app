import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { passesAPI } from '../../services/api';
import { Tooltip } from '../shared';
import { formatPhone } from '../../utils';
import { useAuth } from '../../contexts/authHooks';
import type { PassResponse, WinnerReleaseData, APIError } from '../../types';

interface ReleaseFormState {
  reason: string;
  releasingName: string;
  releasingEmail: string;
  acknowledged: boolean;
}

interface PassReleaseProps {
  pass: PassResponse;
  isAuthenticated: boolean;
  onReleased: (updatedPass: PassResponse) => void;
}

const PassReleaseForm = ({ pass, isAuthenticated, onReleased }: PassReleaseProps) => {
  const [form, setForm] = useState<ReleaseFormState>({
    reason: '',
    releasingName: '',
    releasingEmail: '',
    acknowledged: false,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isClosed = pass.show_status === 'closed';

  const handleRelease = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!form.acknowledged) {
      setError('Please acknowledge that the promotions owner will be notified.');
      return;
    }
    if (!form.reason.trim()) {
      setError('Reason is required.');
      return;
    }
    if (!isAuthenticated) {
      if (!form.releasingName.trim()) {
        setError('Your name is required.');
        return;
      }
      if (!form.releasingEmail.trim()) {
        setError('Your email address is required.');
        return;
      }
    }

    const releaseData: WinnerReleaseData = {
      reason: form.reason.trim(),
    };
    if (!isAuthenticated) {
      releaseData.releasing_name = form.releasingName.trim();
      releaseData.releasing_email = form.releasingEmail.trim();
    }

    try {
      setLoading(true);
      const updated = await passesAPI.releaseWinner(pass.id, releaseData);
      onReleased(updated);
    } catch (err) {
      const apiError = err as APIError;
      setError(
        typeof apiError.detail === 'string' ? apiError.detail : 'Failed to release winner'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleRelease} className="winner-release-form">
      <div className="acknowledgment-notice">
        <label className="override-label">
          <input
            type="checkbox"
            checked={form.acknowledged}
            onChange={(e) => setForm((prev) => ({ ...prev, acknowledged: e.target.checked }))}
            disabled={loading || isClosed}
          />
          I understand that the promotions owner will be notified of this release.
        </label>
      </div>

      <div className="form-group">
        <div className="label-with-help">
          <label htmlFor={`reason-${pass.id}`}>Reason *</label>
          <Tooltip text='Explain why you are releasing these passes. Example: "The pass winner called in and is no longer available to go to the show and they wanted us to be able to give the passes away to someone else."' />
        </div>
        <textarea
          id={`reason-${pass.id}`}
          value={form.reason}
          onChange={(e) => setForm((prev) => ({ ...prev, reason: e.target.value }))}
          disabled={loading || isClosed}
          placeholder="Describe why these passes are being released..."
          rows={3}
        />
      </div>

      {!isAuthenticated && (
        <>
          <div className="form-group">
            <label htmlFor={`releasing-name-${pass.id}`}>Your Name *</label>
            <input
              type="text"
              id={`releasing-name-${pass.id}`}
              value={form.releasingName}
              onChange={(e) => setForm((prev) => ({ ...prev, releasingName: e.target.value }))}
              disabled={loading || isClosed}
              placeholder="Enter your name"
            />
          </div>
          <div className="form-group">
            <label htmlFor={`releasing-email-${pass.id}`}>Your Email *</label>
            <input
              type="email"
              id={`releasing-email-${pass.id}`}
              value={form.releasingEmail}
              onChange={(e) => setForm((prev) => ({ ...prev, releasingEmail: e.target.value }))}
              disabled={loading || isClosed}
              placeholder="Enter your email address"
            />
          </div>
        </>
      )}

      {error && <div className="error-message">{error}</div>}

      <div className="form-actions">
        <button
          type="submit"
          className="btn-danger"
          disabled={loading || isClosed}
          title={
            isClosed
              ? "This show is closed. The winner's name has already been sent to the venue and cannot be undone."
              : undefined
          }
        >
          {loading ? 'Releasing...' : 'Release Passes'}
        </button>
      </div>

      {isClosed && (
        <p className="closed-notice">
          This show is closed. The winner&apos;s name has already been sent to the venue and the
          passes cannot be released.
        </p>
      )}
    </form>
  );
};

interface PassResultProps {
  pass: PassResponse;
  isAuthenticated: boolean;
  onReleased: (updatedPass: PassResponse) => void;
}

const PassResult = ({ pass, isAuthenticated, onReleased }: PassResultProps) => {
  const [released, setReleased] = useState(false);

  const handleReleased = (updatedPass: PassResponse) => {
    setReleased(true);
    onReleased(updatedPass);
  };

  return (
    <div className={`pass-result-card${released ? ' pass-result-released' : ''}`}>
      <div className="pass-result-header">
        <h3 className="pass-result-show">
          {pass.show_event_name ? (
            <Link to={`/dj/shows/${pass.show_id}`}>{pass.show_event_name}</Link>
          ) : (
            `Show #${pass.show_id}`
          )}
        </h3>
        {pass.show_status && (
          <span className={`status-badge status-${pass.show_status}`}>
            {pass.show_status}
          </span>
        )}
      </div>

      <dl className="pass-result-details">
        <dt>Venue</dt>
        <dd>{pass.show_venue_name ?? '—'}</dd>
        <dt>Show Date</dt>
        <dd>{pass.show_date ?? '—'}</dd>
        <dt>Winner Name</dt>
        <dd>{pass.recipient_name ?? '—'}</dd>
        <dt>Winner Phone</dt>
        <dd>{formatPhone(pass.recipient_phone)}</dd>
        <dt>Given Away By</dt>
        <dd>{pass.given_away_by_dj ?? '—'}</dd>
        <dt>Given Away At</dt>
        <dd>{pass.given_away_at ? new Date(pass.given_away_at).toLocaleString('en-US', { timeZone: 'America/Los_Angeles' }) : '—'}</dd>
      </dl>

      {released ? (
        <div className="success-message">Passes successfully released and available for re-giveaway.</div>
      ) : pass.status === 'given_away' ? (
        <div className="release-section">
          <h4>Release These Passes</h4>
          <div className="caller-verification-notice">
            <strong>Verify the caller before releasing.</strong> Ask the caller to confirm details
            about the show they won passes for — such as the show name, venue, or date. Someone who
            simply has the winner&apos;s phone number would not know these details.
          </div>
          <PassReleaseForm
            pass={pass}
            isAuthenticated={isAuthenticated}
            onReleased={handleReleased}
          />
        </div>
      ) : (
        <p className="pass-status-notice">
          Pass status: <strong>{pass.status}</strong> — no winner to release.
        </p>
      )}
    </div>
  );
};

const WinnerSearch = () => {
  const { user } = useAuth();
  const isAuthenticated = !!user?.email;

  const [phone, setPhone] = useState('');
  const [passes, setPasses] = useState<PassResponse[]>([]);
  const [searched, setSearched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rateLimitSeconds, setRateLimitSeconds] = useState(0);

  useEffect(() => {
    if (rateLimitSeconds <= 0) return;
    const timer = setInterval(() => {
      setRateLimitSeconds((prev) => (prev <= 1 ? 0 : prev - 1));
    }, 1000);
    return () => clearInterval(timer);
  }, [rateLimitSeconds]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedPhone = phone.trim();
    if (!trimmedPhone) {
      setError('Please enter a phone number.');
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const results = await passesAPI.searchByPhone(trimmedPhone);
      setPasses(results);
      setSearched(true);
    } catch (err) {
      const apiError = err as APIError;
      if (typeof apiError.retry_after === 'number') {
        setRateLimitSeconds(apiError.retry_after);
      } else {
        setError(
          typeof apiError.detail === 'string' ? apiError.detail : 'Search failed'
        );
      }
    } finally {
      setLoading(false);
    }
  };

  const handlePassReleased = (updatedPass: PassResponse) => {
    setPasses((prev) => prev.map((p) => (p.id === updatedPass.id ? updatedPass : p)));
  };

  return (
    <div className="winner-search-page">
      <h2>Winner Pass Search</h2>
      <p className="page-description">
        Search for a pass winner by their phone number to find passes they won. If the show is
        not yet closed, you can release their passes so they become available for re-giveaway.
      </p>

      <form onSubmit={handleSearch} className="winner-search-form">
        <div className="form-group search-input-group">
          <label htmlFor="winner-phone">Phone Number</label>
          <div className="search-input-row">
            <input
              type="tel"
              id="winner-phone"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              disabled={loading || rateLimitSeconds > 0}
              placeholder="Enter winner's phone number"
              autoComplete="off"
            />
            <button
              type="submit"
              className="btn-primary"
              disabled={loading || rateLimitSeconds > 0}
            >
              {loading ? 'Searching...' : rateLimitSeconds > 0 ? `Wait ${rateLimitSeconds}s` : 'Search'}
            </button>
          </div>
        </div>
        {rateLimitSeconds > 0 && (
          <div className="error-message">
            Too many searches. Please wait {rateLimitSeconds} second{rateLimitSeconds !== 1 ? 's' : ''} before trying again.
          </div>
        )}
        {error && <div className="error-message">{error}</div>}
      </form>

      {searched && (
        <div className="winner-search-results">
          {passes.length === 0 ? (
            <p className="no-results">No pass winners found for that phone number.</p>
          ) : (() => {
            const releasablePasses = passes.filter((p) => p.show_status !== 'closed');
            if (releasablePasses.length === 0) {
              return (
                <p className="no-results">
                  No releasable passes found. All matching passes are for closed shows.
                </p>
              );
            }
            return (
              <>
                <p className="results-count">
                  Found {releasablePasses.length} pass{releasablePasses.length !== 1 ? 'es' : ''} for this phone number.
                </p>
                <div className="pass-results-list">
                  {releasablePasses.map((pass) => (
                    <PassResult
                      key={pass.id}
                      pass={pass}
                      isAuthenticated={isAuthenticated}
                      onReleased={handlePassReleased}
                    />
                  ))}
                </div>
              </>
            );
          })()}
        </div>
      )}
    </div>
  );
};

export default WinnerSearch;
