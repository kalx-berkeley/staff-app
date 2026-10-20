import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { usePageTitle } from '../common/hooks/usePageTitle';
import { reviewAPI } from './api';
import type { DepartmentPeople, ReviewOverview } from './types';
import { errorMessage, formatHours, formatMonth } from './utils';
import { WORKFORMS_TITLE } from './WorkformsLayout';

const MAX_MONTHS = 12;
const DEFAULT_MONTHS = 3;
const DEFAULT_MIN_MONTHS = 2;

/** "2026-09" → "Sep 2026". */
function formatMonthShort(month: string): string {
  const [year, m] = month.split('-').map(Number);
  return new Date(year, m - 1, 1).toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
}

/** A whole number from *value* between 1 and *max*, or *fallback*. */
function clampCount(value: string | null, max: number, fallback: number): number {
  const n = Number(value);
  return Number.isInteger(n) && n >= 1 ? Math.min(n, max) : Math.min(fallback, max);
}

const range = (n: number) => Array.from({ length: n }, (_, i) => i + 1);

// Who works in a department: everyone who reported hours in it in at least
// some of the most recent months, with their hours in each month.
export default function PeoplePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [overview, setOverview] = useState<ReviewOverview | null>(null);
  const [result, setResult] = useState<DepartmentPeople | null>(null);
  const [error, setError] = useState<string | null>(null);
  usePageTitle('People', WORKFORMS_TITLE);

  const months = clampCount(searchParams.get('months'), MAX_MONTHS, DEFAULT_MONTHS);
  const minMonths = clampCount(searchParams.get('min'), months, DEFAULT_MIN_MONTHS);
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
    setResult(null);
    reviewAPI
      .people(department, months, minMonths)
      .then((loaded) => {
        if (!current) return;
        setResult(loaded);
        setError(null);
      })
      .catch((e) => current && setError(errorMessage(e)));
    return () => {
      current = false;
    };
  }, [department, months, minMonths, overview]);

  if (error && !overview) return <div className="error-message">{error}</div>;
  if (!overview || !department) return <p className="workforms-loading">Loading…</p>;

  const update = (changes: Record<string, string | number>) => {
    const next = { department, months: String(months), min: String(minMonths) };
    for (const [key, value] of Object.entries(changes)) {
      next[key as keyof typeof next] = String(value);
    }
    setSearchParams(next);
  };

  return (
    <div className="workforms-people">
      <div className="workforms-review-toolbar">
        <label>
          Department
          <select value={department} onChange={(e) => update({ department: e.target.value })}>
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
        <label>
          Months with hours
          <select value={minMonths} onChange={(e) => update({ min: e.target.value })}>
            {range(months).map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <label>
          Out of the last
          <select
            value={months}
            onChange={(e) => {
              const n = Number(e.target.value);
              update({ months: n, min: Math.min(minMonths, n) });
            }}
          >
            {range(MAX_MONTHS).map((n) => (
              <option key={n} value={n}>
                {n} {n === 1 ? 'month' : 'months'}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error && (
        <div className="error-message" role="alert">
          {error}
        </div>
      )}

      {!result ? (
        <p className="workforms-loading">Loading…</p>
      ) : (
        <>
          <p className="workforms-hint">
            People who reported {result.department} hours in at least {result.min_months} of the{' '}
            {result.months.length === 1
              ? `month of ${formatMonth(result.months[0])}`
              : `${result.months.length} months from ${formatMonth(result.months[0])} to ${formatMonth(result.months[result.months.length - 1])}`}
            , whether or not the hours were approved. This month isn't counted until it's over.
          </p>
          {result.people.length === 0 ? (
            <p className="workforms-empty">No one matches.</p>
          ) : (
            <div className="workforms-people-scroll">
              <table className="workforms-people-table">
                <thead>
                  <tr>
                    <th scope="col">
                      {result.people.length} {result.people.length === 1 ? 'person' : 'people'}
                    </th>
                    {result.months.map((m) => (
                      <th key={m} scope="col" className="workforms-people-month">
                        {formatMonthShort(m)}
                      </th>
                    ))}
                    <th scope="col" className="workforms-people-month">
                      Total
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {result.people.map((person) => (
                    <tr key={person.staff_id ?? person.staff_name}>
                      <th scope="row">
                        {person.staff_name}{' '}
                        {!person.is_current_staff && (
                          <span className="leave-badge">Not current staff</span>
                        )}
                      </th>
                      {result.months.map((m) => (
                        <td
                          key={m}
                          className={
                            m in person.hours
                              ? 'workforms-people-hours workforms-people-worked'
                              : 'workforms-people-hours'
                          }
                        >
                          {m in person.hours ? `${formatHours(person.hours[m])} h` : '—'}
                        </td>
                      ))}
                      <td className="workforms-people-hours workforms-people-total">
                        {formatHours(person.total_hours)} h
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
