import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { specialtyShowsAPI } from '../api';
import { useAuth } from '../../common/contexts/authHooks';
import { usePageTitle } from '../../common/hooks/usePageTitle';
import { SPECIALTY_SHOW_KINDS } from '../utils';
import type { SpecialtyShowCategory, SpecialtyShowResponse } from '../types';
import type { APIError } from '../../common/types';

const HINTS: Record<SpecialtyShowCategory, string> = {
  music:
    'Specialty Music Shows are on-air DJ shows that can receive pre-assigned pass pairs.',
  talk:
    'Talk & Info Shows are on-air talk and information shows (news, sports, public affairs and so ' +
    'on) that can receive pre-assigned pass pairs. Their staff members can reserve passes for ' +
    'the show, whether or not they are DJs.',
};

interface SpecialtyShowListProps {
  /** Which kind of show this page lists. */
  category?: SpecialtyShowCategory;
}

/** The list of Specialty Music Shows or of Talk & Info Shows, by `category`. */
const SpecialtyShowList = ({ category = 'music' }: SpecialtyShowListProps) => {
  const kind = SPECIALTY_SHOW_KINDS[category];
  usePageTitle(`${kind.plural} · Staff`);
  const navigate = useNavigate();
  const { user } = useAuth();
  const isPromotions = user?.role === 'promotions';

  const [shows, setShows] = useState<SpecialtyShowResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newName, setNewName] = useState('');
  const [newSpinitronUrl, setNewSpinitronUrl] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);

  const [upcomingTitles, setUpcomingTitles] = useState<string[]>([]);
  const [titleSuggestions, setTitleSuggestions] = useState<string[]>([]);
  const [showTitleSuggestions, setShowTitleSuggestions] = useState(false);
  const [myMemberShowIds, setMyMemberShowIds] = useState<Set<number>>(new Set());

  const loadShows = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await specialtyShowsAPI.list(true, category);
      setShows(data);
    } catch (err) {
      const apiError = err as APIError;
      setError(typeof apiError.detail === 'string' ? apiError.detail : `Failed to load ${kind.plural}`);
    } finally {
      setLoading(false);
    }
  }, [category, kind.plural]);

  useEffect(() => {
    loadShows();
    specialtyShowsAPI.getUpcomingTitles().then(setUpcomingTitles).catch(() => {});
    specialtyShowsAPI
      .listMine()
      .then((mine) =>
        setMyMemberShowIds(
          new Set(mine.filter((s) => s.is_dj || s.is_staff_member).map((s) => s.id)),
        ),
      )
      .catch(() => {});
  }, [loadShows]);

  const isOwner = (show: SpecialtyShowResponse) =>
    user?.email ? show.owner_emails.includes(user.email) : false;

  const canManage = (show: SpecialtyShowResponse) => isPromotions || isOwner(show);

  const isMyShow = (show: SpecialtyShowResponse) => myMemberShowIds.has(show.id);

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
    const spinitronUrl = newSpinitronUrl.trim();
    if (!name || !spinitronUrl) return;
    setSubmitting(true);
    setFormError(null);
    setShowTitleSuggestions(false);
    try {
      const created = await specialtyShowsAPI.create({
        name,
        category,
        spinitron_urls: [spinitronUrl],
      });
      navigate(`${kind.path}/${created.id}`);
    } catch (err) {
      const apiError = err as APIError;
      setFormError(typeof apiError.detail === 'string' ? apiError.detail : `Failed to create ${kind.label}`);
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
      setFormError(typeof apiError.detail === 'string' ? apiError.detail : `Failed to delete ${kind.label}`);
      setDeleteConfirmId(null);
    } finally {
      setDeleting(false);
    }
  };

  const handleSetRetired = async (id: number, retired: boolean) => {
    setFormError(null);
    try {
      await specialtyShowsAPI.setRetired(id, retired);
      await loadShows();
    } catch (err) {
      const apiError = err as APIError;
      setFormError(
        typeof apiError.detail === 'string'
          ? apiError.detail
          : `Failed to ${retired ? 'retire' : 'un-retire'} ${kind.label}`,
      );
    }
  };

  if (loading) return <div className="loading">Loading {kind.plural}...</div>;

  if (error) {
    return (
      <div className="error">
        <p>Error: {error}</p>
        <button onClick={loadShows}>Retry</button>
      </div>
    );
  }

  const deleteTarget = shows.find((s) => s.id === deleteConfirmId);
  const currentShows = shows.filter((s) => !s.retired);
  const retiredShows = shows.filter((s) => s.retired);
  const missingSpinitron = shows.filter((s) => s.spinitron_shows.length === 0);

  return (
    <div className="venue-list">
      <div className="venue-list-header">
        <h2>{kind.plural}</h2>
      </div>

      <p className="field-hint">
        {HINTS[category]} Their names appear alongside DJ names in all DJ name autocomplete
        fields. When adding one, use its exact on-air schedule name (the "New{' '}
        {kind.label} name" field suggests titles from the upcoming Spinitron schedule) so it
        matches.
        Each show also needs its Spinitron link (a show or playlist page), which is how the
        Staff Directory tells {kind.plural} apart from regular DJ shifts. Retire a show
        when it ends: it stays on record but can no longer get passes.
      </p>

      {missingSpinitron.length > 0 && (
        <div className="field-warning" role="alert">
          These shows don't have a Spinitron link yet, so their playlists count as regular DJ
          shifts for the DJ sublist: {missingSpinitron.map((s) => s.name).join(', ')}. Open each
          one to add it.
        </div>
      )}

      {isPromotions && (
        <form onSubmit={handleCreate} className="venue-filter" style={{ alignItems: 'flex-start', gap: '0.5rem' }}>
          <div className="autocomplete-wrapper">
            <input
              type="text"
              placeholder={`New ${kind.label} name...`}
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
          <input
            type="url"
            placeholder="Spinitron show or playlist link"
            aria-label="Spinitron show or playlist link"
            value={newSpinitronUrl}
            onChange={(e) => setNewSpinitronUrl(e.target.value)}
            className="venue-filter-input"
            disabled={submitting}
          />
          <button
            type="submit"
            className="btn-primary"
            disabled={submitting || !newName.trim() || !newSpinitronUrl.trim()}
          >
            {submitting ? 'Adding...' : 'Add'}
          </button>
          {formError && (
            <span className="field-error" style={{ alignSelf: 'center' }}>{formError}</span>
          )}
        </form>
      )}

      {currentShows.length === 0 ? (
        <p className="empty-message">No {kind.plural} yet.</p>
      ) : (
        <div className="venue-grid">
          {currentShows.map((show) => (
            <div key={show.id} className="venue-card">
              <h3>{show.name}</h3>
              {isMyShow(show) && (
                <span className="status-badge status-dj">
                  {category === 'talk' ? "You're on this show's staff" : "You're a DJ for this show"}
                </span>
              )}
              {canManage(show) ? (
                <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
                  <Link to={`${kind.path}/${show.id}`} className="btn-primary btn-small">
                    Manage
                  </Link>
                  <button
                    onClick={() => handleSetRetired(show.id, true)}
                    className="btn-secondary btn-small"
                  >
                    Retire
                  </button>
                  {isPromotions && (
                    <button
                      onClick={() => setDeleteConfirmId(show.id)}
                      className="btn-danger btn-small"
                    >
                      Delete
                    </button>
                  )}
                </div>
              ) : (
                <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
                  <Link to={`${kind.path}/${show.id}`} className="btn-secondary btn-small">
                    View
                  </Link>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {retiredShows.length > 0 && (
        <details className="retired-shows">
          <summary>Retired shows ({retiredShows.length})</summary>
          <ul className="item-list">
            {retiredShows.map((show) => (
              <li key={show.id} className="item-list-row">
                <Link to={`${kind.path}/${show.id}`}>{show.name}</Link>
                {canManage(show) && (
                  <button
                    onClick={() => handleSetRetired(show.id, false)}
                    className="btn-secondary btn-small"
                  >
                    Un-retire
                  </button>
                )}
              </li>
            ))}
          </ul>
        </details>
      )}

      {deleteConfirmId !== null && deleteTarget && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <h3>Delete {kind.label}</h3>
            </div>
            <div className="modal-body">
              <p>
                Are you sure you want to delete <strong>{deleteTarget.name}</strong>?
              </p>
              <p>
                This {kind.label} will be removed from all DJ name autocomplete lists.
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

/** The Talk & Info Shows list, at `/staff/talk-shows`. */
export const TalkShowList = () => <SpecialtyShowList category="talk" />;

export default SpecialtyShowList;
