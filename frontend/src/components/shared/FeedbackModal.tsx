import { useState } from 'react';
import { useAuth } from '../../contexts/authHooks';
import { feedbackAPI } from '../../services/api';
import type { APIError } from '../../types';

interface FeedbackModalProps {
  onClose: () => void;
}

const FeedbackModal = ({ onClose }: FeedbackModalProps) => {
  const { user } = useAuth();
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const pageUrl = window.location.href;

  const handleSubmit = async () => {
    if (!message.trim()) {
      setError('Please enter a message before submitting.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await feedbackAPI.submit({ page_url: pageUrl, message: message.trim() });
      setSuccess(true);
      setTimeout(onClose, 2000);
    } catch (err) {
      const apiError = err as APIError;
      setError(
        typeof apiError.detail === 'string'
          ? apiError.detail
          : 'Failed to send feedback. Please try again.'
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Send Feedback / Report a Bug</h3>
          <button className="btn-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <div className="modal-body">
          <div className="feedback-context">
            <p>
              <strong>Page:</strong> {pageUrl}
            </p>
            {user?.email && (
              <p>
                <strong>Logged in as:</strong> {user.email} ({user.role})
              </p>
            )}
          </div>
          <div className="form-group">
            <label htmlFor="feedback-message">Your feedback or bug report:</label>
            <textarea
              id="feedback-message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={6}
              placeholder="Describe what happened or what you'd like to see improved..."
              disabled={submitting || success}
            />
          </div>
          {error && <div className="error-message">{error}</div>}
          {success && (
            <div className="success-message">Feedback sent! Thank you.</div>
          )}
        </div>
        <div className="form-actions">
          <button
            type="button"
            className="btn-secondary"
            onClick={onClose}
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={handleSubmit}
            disabled={submitting || success || !message.trim()}
          >
            {submitting ? 'Sending...' : 'Send Feedback'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default FeedbackModal;
