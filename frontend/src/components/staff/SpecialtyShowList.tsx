import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { specialtyShowsAPI } from '../../services/api';
import { useAuth } from '../../contexts/authHooks';
import type { SpecialtyShowResponse, APIError } from '../../types';

const SpecialtyShowList = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const isPromotions = user?.role === 'promotions';

  const [shows, setShows] = useState<SpecialtyShowResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newName, setNewName] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);

  const [upcomingTitles, setUpcomingTitles] = useState<string[]>([]);
  const [titleSuggestions, setTitleSuggestions] = useState<string[]>([]);
  const [showTitleSuggestions, setShowTitleSuggestions] = useState(false);

  const loadShows = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await specialtyShowsAPI.list();
      setShows(data);
    } catch (err) {
      const apiError = err as APIError;
      setError(typeof apiError.detail === 'string' ? apiError.detail : 'Failed to load specialty shows');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadShows();
    specialtyShowsAPI.getUpcomingTitles().then(setUpcomingTitles).catch(() => {});
  }, [loadShows]);

  const isOwner = (show: SpecialtyShowResponse) =>
    user?.email ? show.owner_emails.includes(user.email) : false;

  const canManage = (show: SpecialtyShowResponse) => isPromotions || isOwner(show);

  const handleNameInputChange = (value: string) => {
    setNewName(value);
    if (value.trim()) {
      const filtered = upcomingTitles.filter((n) => n.toLowerCase().includes(value.toLowerCase()));
      setTitleSuggestions(filtered);
      setShowTitleSuggestions(filtered.length > 0);
    } else {
      setTitleSuggestions([]);
      setShowTitleSuggestions(false);
    }
  };

  const selectTitle = (name: string) => {
    setNewName(name);
    setShowTitleSuggestions(false);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const name = newName.trim();
    if (!name) return;
    setSubmitting(true);
    setFormError(null);
    setShowTitleSuggestions(false);
    try {
      const created = await specialtyShowsAPI.create({ name });
      navigate(`/staff/specialty-shows/${created.id}`);
    } catch (err) {
      const apiError = err as APIError;
      setFormError(typeof apiError.detail === 'string' ? apiError.detail : 'Failed to create specialty show');
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    setDeleting(true);
    try {
      await specialtyShowsAPI.delete(id);
      setDeleteConfirmId(null);
      await loadShows();
    } catch (err) {
      const apiError = err as APIError;
      setFormError(typeof apiError.detail === 'string' ? apiError.detail : 'Failed to delete specialty show');
      setDeleteConfirmId(null);
    } finally {
      setDeleting(false);
    }
  };

  if (loading) return <div className="loading">Loading specialty shows...</div>;

  if (error) {
    return (
      <div className="error">
        <p>Error: {error}</p>
        <button onClick={loadShows}>Retry</button>
      </div>
    );
  }

  const deleteTarget = shows.find((s) => s.id === deleteConfirmId);

  return (
    <div className="venue-list">
      <div className="venue-list-header">
        <h2>Specialty Shows</h2>
      </div>

      <p className="field-hint">
        Specialty shows are on-air DJ shifts that can receive pre-assigned pass pairs.
        Their names appear alongside DJ names in all DJ name autocomplete fields. When
        adding one, use its exact on-air schedule name (the "New specialty show name"
        field suggests titles from the upcoming Spinitron schedule) so it matches.
      </p>

      {isPromotions && (
        <form onSubmit={handleCreate} className="venue-filter" style={{ alignItems: 'flex-start', gap: '0.5rem' }}>
          <div className="autocomplete-wrapper">
            <input
              type="text"
              placeholder="New specialty show name..."
              value={newName}
              onChange={(e) => handleNameInputChange(e.target.value)}
              onFocus={() => { if (newName.trim()) setShowTitleSuggestions(true); }}
              onBlur={() => setTimeout(() => setShowTitleSuggestions(false), 200)}
              className="venue-filter-input"
              disabled={submitting}
              autoComplete="off"
              onKeyDown={(e) => {
                if (e.key === 'Escape') { setShowTitleSuggestions(false); }
                else if (e.key === 'Tab' && titleSuggestions.length === 1) {
                  e.preventDefault();
                  setNewName(titleSuggestions[0]);
                  setShowTitleSuggestions(false);
                }
              }}
            />
            {showTitleSuggestions && titleSuggestions.length > 0 && (
              <ul className="autocomplete-list">
                {titleSuggestions.map((name) => (
                  <li
                    key={name}
                    onMouseDown={() => selectTitle(name)}
                    className="autocomplete-item"
                  >
                    {name}
                  </li>
                ))}
                {titleSuggestions.length === 1 && (
                  <li className="autocomplete-hint">Press Tab to complete</li>
                )}
              </ul>
            )}
          </div>
          <button type="submit" className="btn-primary" disabled={submitting || !newName.trim()}>
            {submitting ? 'Adding...' : 'Add'}
          </button>
          {formError && (
            <span className="field-error" style={{ alignSelf: 'center' }}>{formError}</span>
          )}
        </form>
      )}

      {shows.length === 0 ? (
        <p className="empty-message">No specialty shows yet.</p>
      ) : (
        <div className="venue-grid">
          {shows.map((show) => (
            <div key={show.id} className="venue-card">
              <h3>{show.name}</h3>
              {canManage(show) && (
                <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
                  <Link to={`/staff/specialty-shows/${show.id}`} className="btn-primary btn-small">
                    Manage
                  </Link>
                  {isPromotions && (
                    <button
                      onClick={() => setDeleteConfirmId(show.id)}
                      className="btn-danger btn-small"
                    >
                      Delete
                    </button>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {deleteConfirmId !== null && deleteTarget && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <h3>Delete Specialty Show</h3>
            </div>
            <div className="modal-body">
              <p>
                Are you sure you want to delete <strong>{deleteTarget.name}</strong>?
              </p>
              <p>
                This specialty show will be removed from all DJ name autocomplete lists.
              </p>
            </div>
            <div className="form-actions">
              <button
                type="button"
                onClick={() => setDeleteConfirmId(null)}
                className="btn-secondary"
                disabled={deleting}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => handleDelete(deleteConfirmId)}
                className="btn-danger"
                disabled={deleting}
              >
                {deleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SpecialtyShowList;
