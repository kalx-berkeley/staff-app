import { useId, useState, type FormEvent } from 'react';
import type { Departments, EntryInput } from './types';
import { hoursProblem, monthBounds } from './utils';

interface EntryFormProps {
  month: string;
  departments: Departments;
  initial?: EntryInput;
  submitLabel: string;
  onSave: (entry: EntryInput) => Promise<void>;
  onCancel?: () => void;
}

// Adds or edits one entry: hours in a department, what was done, and
// (recommended, not required) the day it was done, limited to the month.
export default function EntryForm({
  month,
  departments,
  initial,
  submitLabel,
  onSave,
  onCancel,
}: EntryFormProps) {
  const [department, setDepartment] = useState(
    initial?.department ?? departments.own[0] ?? departments.other[0] ?? ''
  );
  const [hours, setHours] = useState(initial ? String(initial.hours) : '');
  const [workDate, setWorkDate] = useState(initial?.work_date ?? '');
  const [description, setDescription] = useState(initial?.description ?? '');
  const [problem, setProblem] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const { min, max } = monthBounds(month);
  const id = useId();

  const save = async (event: FormEvent) => {
    event.preventDefault();
    const issue =
      (!department && 'Choose a department') ||
      hoursProblem(hours) ||
      (!description.trim() && 'Describe the work you did') ||
      null;
    setProblem(issue);
    if (issue) return;
    setSaving(true);
    try {
      await onSave({
        department,
        hours: Number(hours),
        description: description.trim(),
        work_date: workDate || null,
      });
      if (!initial) {
        // Keep the department for the next entry; clear the rest.
        setHours('');
        setWorkDate('');
        setDescription('');
      }
    } catch (error) {
      setProblem(error instanceof Error ? error.message : String(error));
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="workforms-entry-form" onSubmit={save} noValidate>
      <div className="workforms-entry-fields">
        <label htmlFor={`${id}-department`}>
          Department
          <select
            id={`${id}-department`}
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
          >
            {departments.own.length > 0 && (
              <optgroup label="Your departments">
                {departments.own.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </optgroup>
            )}
            {departments.other.length > 0 && (
              <optgroup label={departments.own.length ? 'Other departments' : 'Departments'}>
                {departments.other.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </optgroup>
            )}
          </select>
        </label>
        <label htmlFor={`${id}-hours`}>
          Hours
          <input
            id={`${id}-hours`}
            type="number"
            inputMode="decimal"
            min="0.25"
            step="0.25"
            value={hours}
            onChange={(e) => setHours(e.target.value)}
          />
        </label>
        <label htmlFor={`${id}-date`}>
          <span>
            Date <span className="workforms-recommended">(recommended)</span>
          </span>
          <input
            id={`${id}-date`}
            type="date"
            min={min}
            max={max}
            value={workDate}
            onChange={(e) => setWorkDate(e.target.value)}
          />
        </label>
      </div>
      <label htmlFor={`${id}-description`} className="workforms-entry-description">
        What did you do?
        <textarea
          id={`${id}-description`}
          rows={2}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="For example: ran the KALX table at the Sproul Halloween event"
        />
      </label>
      {problem && (
        <div className="error-message" role="alert">
          {problem}
        </div>
      )}
      <div className="workforms-entry-actions">
        <button type="submit" className="btn-primary" disabled={saving}>
          {saving ? 'Saving…' : submitLabel}
        </button>
        {onCancel && (
          <button type="button" className="btn-secondary" onClick={onCancel} disabled={saving}>
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
