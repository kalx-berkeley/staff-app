import { useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import type { APIError } from '../../../common/types';

interface EntityFormPageProps {
  /** What is being edited, such as "Venue". */
  noun: string;
  /** The saved name when editing, or null for a new one. */
  savedName: string | null;
  apiError: string | null;
  submitting: boolean;
  onSubmit: (e: FormEvent) => void;
  onCancel: () => void;
  /** Deletes the saved one. Leave out for a new one. */
  onDelete?: () => Promise<void>;
  /** Extra paragraphs for the delete confirmation. */
  deleteNote?: ReactNode;
  children: ReactNode;
}

/**
 * The page around the venue and promoter forms: the heading, the error, the
 * Delete / Cancel / Create buttons and the delete confirmation.
 */
const EntityFormPage = ({
  noun,
  savedName,
  apiError,
  submitting,
  onSubmit,
  onCancel,
  onDelete,
  deleteNote,
  children,
}: EntityFormPageProps) => {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const editing = savedName != null;
  const busy = submitting || deleting;

  const handleDelete = async () => {
    if (!onDelete) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await onDelete();
    } catch (err) {
      const error = err as APIError;
      setShowDeleteConfirm(false);
      setDeleteError(
        typeof error.detail === 'string' ? error.detail : `Failed to delete ${noun.toLowerCase()}`
      );
    } finally {
      setDeleting(false);
    }
  };

  const error = apiError ?? deleteError;

  return (
    <div className="venue-form-page">
      <h2>{editing ? `Edit ${noun}: ${savedName}` : `New ${noun}`}</h2>
      <form onSubmit={onSubmit} className="venue-form">
        {error && <div className="error-message">{error}</div>}

        {children}

        <div className="form-actions">
          {editing && onDelete && (
            <button
              type="button"
              onClick={() => setShowDeleteConfirm(true)}
              className="btn-danger"
              disabled={busy}
            >
              Delete
            </button>
          )}
          <button type="button" onClick={onCancel} className="btn-secondary" disabled={busy}>
            Cancel
          </button>
          <button type="submit" className="btn-primary" disabled={busy}>
            {submitting ? 'Saving...' : `${editing ? 'Update' : 'Create'} ${noun}`}
          </button>
        </div>
      </form>

      {showDeleteConfirm && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <h3>Delete {noun}</h3>
            </div>
            <div className="modal-body">
              <p>
                Are you sure you want to delete <strong>{savedName}</strong>?
              </p>
              <p>
                This {noun.toLowerCase()} will be hidden from all lists and dropdowns. It can be
                restored later from the Admin page.
              </p>
              {deleteNote}
            </div>
            <div className="form-actions">
              <button
                type="button"
                onClick={() => setShowDeleteConfirm(false)}
                className="btn-secondary"
                disabled={deleting}
              >
                Cancel
              </button>
              <button type="button" onClick={handleDelete} className="btn-danger" disabled={deleting}>
                {deleting ? 'Deleting...' : `Delete ${noun}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default EntityFormPage;
