import { useEffect, useState } from 'react';
import { errorMessage } from '../common/utils';
import { adminAPI } from './api';
import type { DjQuizDeadline } from './types';

const byYearDesc = (a: DjQuizDeadline, b: DjQuizDeadline) => b.year - a.year;

const formatDeadline = (value: string) => {
  const [year, month, day] = value.split('-').map(Number);
  return new Date(year, month - 1, day).toLocaleDateString('en-US', { dateStyle: 'long' });
};

// Site admins only: when each year's DJ Quiz is due. The Staff Directory's
// Sublist DJ requirements count last year's quiz until this year's deadline
// passes, and only this year's after it.
export default function DjQuizDeadlinesSection() {
  const [deadlines, setDeadlines] = useState<DjQuizDeadline[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [year, setYear] = useState(String(new Date().getFullYear() + 1));
  const [deadline, setDeadline] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    adminAPI
      .listDjQuizDeadlines()
      .then(setDeadlines)
      .catch((err) => setError(errorMessage(err)));
  }, []);

  const save = async (saveYear: number, saveDeadline: string) => {
    setSaving(true);
    setError(null);
    try {
      const saved = await adminAPI.setDjQuizDeadline(saveYear, saveDeadline);
      setDeadlines((prev) =>
        [...(prev ?? []).filter((d) => d.year !== saved.year), saved].sort(byYearDesc),
      );
      return true;
    } catch (err) {
      setError(errorMessage(err));
      return false;
    } finally {
      setSaving(false);
    }
  };

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (await save(Number(year), deadline)) setDeadline('');
  };

  const handleRemove = async (removeYear: number) => {
    if (!window.confirm(`Remove the ${removeYear} DJ Quiz deadline?`)) return;
    setSaving(true);
    setError(null);
    try {
      await adminAPI.deleteDjQuizDeadline(removeYear);
      setDeadlines((prev) => (prev ?? []).filter((d) => d.year !== removeYear));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="admin-section">
      <h2>DJ Quiz Deadlines</h2>
      <p className="field-hint">
        The last day to complete each year's DJ Quiz. A Sublist DJ's quiz from last year still
        counts until this year's deadline passes; after that only this year's counts. Without a
        deadline for this year, last year's quiz keeps counting.
      </p>

      <form className="short-links-form" onSubmit={handleAdd}>
        <input
          type="number"
          aria-label="Year"
          min={2000}
          max={2100}
          value={year}
          onChange={(e) => setYear(e.target.value)}
          required
        />
        <input
          type="date"
          aria-label="Deadline"
          value={deadline}
          onChange={(e) => setDeadline(e.target.value)}
          required
        />
        <button type="submit" className="btn-primary" disabled={saving}>
          Set deadline
        </button>
      </form>
      {error && <div className="error-message">{error}</div>}

      {deadlines === null ? (
        !error && <p>Loading DJ Quiz deadlines…</p>
      ) : deadlines.length === 0 ? (
        <p>No deadlines yet.</p>
      ) : (
        <table className="audit-log-table">
          <thead>
            <tr>
              <th>Year</th>
              <th>Due by the end of</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {deadlines.map((d) => (
              <tr key={d.year}>
                <td>{d.year}</td>
                <td>{formatDeadline(d.deadline)}</td>
                <td>
                  <button
                    type="button"
                    className="btn-secondary btn-small"
                    onClick={() => {
                      setYear(String(d.year));
                      setDeadline(d.deadline);
                    }}
                    disabled={saving}
                  >
                    Change
                  </button>{' '}
                  <button
                    type="button"
                    className="btn-danger btn-small"
                    onClick={() => handleRemove(d.year)}
                    disabled={saving}
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
