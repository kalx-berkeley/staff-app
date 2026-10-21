import { useEffect, useState, type FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { usePageTitle } from '../common/hooks/usePageTitle';
import { reviewAPI } from './api';
import type { ReviewOverview, WorkTypes } from './types';
import { errorMessage } from './utils';
import { WORKFORMS_TITLE } from './WorkformsLayout';

// The types of work a department head offers staff logging hours in their
// department, and whether staff may describe other work in their own words.
export default function WorkTypesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [overview, setOverview] = useState<ReviewOverview | null>(null);
  const [draft, setDraft] = useState<WorkTypes | null>(null);
  const [newType, setNewType] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  usePageTitle('Work types', WORKFORMS_TITLE);

  const department = searchParams.get('department') ?? overview?.own_departments[0] ?? null;

  useEffect(() => {
    reviewAPI
      .overview()
      .then(setOverview)
      .catch((e) => setError(errorMessage(e)));
  }, []);

  useEffect(() => {
    if (!department || !overview) return;
    let current = true;
    setDraft(null);
    setSaved(false);
    reviewAPI
      .workTypes(department)
      .then((loaded) => {
        if (!current) return;
        setDraft(loaded);
        setError(null);
      })
      .catch((e) => current && setError(errorMessage(e)));
    return () => {
      current = false;
    };
  }, [department, overview]);

  if (error && !overview) return <div className="error-message">{error}</div>;
  if (!overview || !department) return <p className="workforms-loading">Loading…</p>;

  const change = (changes: Partial<WorkTypes>) => {
    setDraft((d) => d && { ...d, ...changes });
    setSaved(false);
  };

  const move = (index: number, by: number) => {
    if (!draft) return;
    const types = [...draft.work_types];
    [types[index], types[index + by]] = [types[index + by], types[index]];
    change({ work_types: types });
  };

  const add = (event: FormEvent) => {
    event.preventDefault();
    const name = newType.trim().replace(/\s+/g, ' ');
    if (!draft || !name) return;
    if (draft.work_types.some((t) => t.toLowerCase() === name.toLowerCase())) {
      setError(`“${name}” is already a work type`);
      return;
    }
    change({ work_types: [...draft.work_types, name] });
    setNewType('');
    setError(null);
  };

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    try {
      setDraft(await reviewAPI.updateWorkTypes(department, draft));
      setError(null);
      setSaved(true);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="workforms-work-types">
      <div className="workforms-review-toolbar">
        <label>
          Department
          <select
            value={department}
            onChange={(e) => setSearchParams({ department: e.target.value })}
          >
            <optgroup label="Your departments">
              {overview.own_departments.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </optgroup>
            {overview.fallback_departments.length > 0 && (
              <optgroup label="Other departments (as Operations)">
                {overview.fallback_departments.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </optgroup>
            )}
          </select>
        </label>
      </div>

      {!draft ? (
        error ? (
          <div className="error-message" role="alert">
            {error}
          </div>
        ) : (
          <p className="workforms-loading">Loading…</p>
        )
      ) : (
        <section className="workforms-card" aria-labelledby="work-types-heading">
          <h3 id="work-types-heading">Types of work in {department}</h3>
          <p className="workforms-hint">
            Staff logging {department} hours choose what they did from these. With none, they
            describe their work in their own words. Changes apply to entries added or edited from
            now on.
          </p>

          {draft.work_types.length === 0 ? (
            <p className="workforms-empty">No work types yet.</p>
          ) : (
            <ul className="workforms-work-type-list">
              {draft.work_types.map((name, index) => (
                <li key={name}>
                  <span>{name}</span>
                  <span className="workforms-entry-buttons">
                    <button
                      type="button"
                      className="btn-secondary btn-small"
                      aria-label={`Move ${name} up`}
                      disabled={index === 0}
                      onClick={() => move(index, -1)}
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      className="btn-secondary btn-small"
                      aria-label={`Move ${name} down`}
                      disabled={index === draft.work_types.length - 1}
                      onClick={() => move(index, 1)}
                    >
                      ↓
                    </button>
                    <button
                      type="button"
                      className="btn-danger btn-small"
                      aria-label={`Remove ${name}`}
                      onClick={() =>
                        change({ work_types: draft.work_types.filter((_, i) => i !== index) })
                      }
                    >
                      Remove
                    </button>
                  </span>
                </li>
              ))}
            </ul>
          )}

          <form className="workforms-work-type-add" onSubmit={add}>
            <input
              aria-label="New work type"
              value={newType}
              maxLength={100}
              onChange={(e) => setNewType(e.target.value)}
              placeholder="For example: Filing CDs"
            />
            <button type="submit" className="btn-secondary" disabled={!newType.trim()}>
              Add
            </button>
          </form>

          <label className="workforms-work-type-free-text">
            <input
              type="checkbox"
              checked={draft.allow_free_text}
              onChange={(e) => change({ allow_free_text: e.target.checked })}
            />{' '}
            Staff can also describe other work in their own words
          </label>
          {!draft.allow_free_text && draft.work_types.length === 0 && (
            <p className="workforms-hint">
              Add at least one work type before requiring staff to choose one.
            </p>
          )}

          {error && (
            <div className="error-message" role="alert">
              {error}
            </div>
          )}
          <div className="workforms-entry-actions">
            <button type="button" className="btn-primary" disabled={saving} onClick={save}>
              {saving ? 'Saving…' : 'Save'}
            </button>
            {saved && (
              <span className="workforms-hint" role="status">
                Saved.
              </span>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
