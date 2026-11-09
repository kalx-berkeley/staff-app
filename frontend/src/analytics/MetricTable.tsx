import { Fragment, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { formatValue, sortValue } from './format';
import { windowQuery } from './timeWindow';
import type { MetricColumn, MetricRow } from './types';

/** Numbers line up on the right, text on the left. */
const isNumeric = (column: MetricColumn) => column.format !== 'text' && column.format !== 'date';

const fillLink = (template: string, row: MetricRow) =>
  template.replace(/\{(\w+)\}/g, (_, key: string) => String(row[key] ?? ''));

function Cell({ column, row }: { column: MetricColumn; row: MetricRow }) {
  const { search } = useLocation();
  const value = row[column.key];
  const text = formatValue(value, column.format);
  if (column.format === 'points' && typeof value === 'number') {
    return <BalanceBar value={value} />;
  }
  if (column.link && value !== null && value !== undefined) {
    return (
      <Link to={`${fillLink(column.link, row)}${windowQuery(new URLSearchParams(search))}`}>
        {text}
      </Link>
    );
  }
  return <>{text}</>;
}

/** Percentage points from −100 to +100, drawn either side of 0. */
export function BalanceBar({ value }: { value: number }) {
  const clamped = Math.max(-100, Math.min(100, value));
  const width = `${Math.abs(clamped) / 2}%`;
  return (
    <span className="analytics-balance" title={formatValue(value, 'points')}>
      <span className="analytics-balance-track">
        <span
          className={`analytics-balance-bar ${clamped >= 0 ? 'on-air' : 'staff'}`}
          style={clamped >= 0 ? { left: '50%', width } : { right: '50%', width }}
        />
      </span>
      <span className="analytics-balance-label">{formatValue(value, 'points')}</span>
    </span>
  );
}

// A metric table: sortable columns, the first `top` rows with "Show all",
// expandable detail rows, and low-sample and highlighted rows.
export default function MetricTable({
  columns,
  rows,
  top,
  label,
}: {
  columns: MetricColumn[];
  rows: MetricRow[];
  top?: number | null;
  label: string;
}) {
  const [sort, setSort] = useState<{ key: string; desc: boolean } | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const hasDetails = rows.some((r) => r._details);
  const hasLowSample = rows.some((r) => r._low_sample);

  const sorted = useMemo(() => {
    if (!sort) return rows.map((row, index) => ({ row, index }));
    return rows
      .map((row, index) => ({ row, index }))
      .sort((a, b) => {
        const av = sortValue(a.row[sort.key]);
        const bv = sortValue(b.row[sort.key]);
        if (av === bv) return 0;
        if (av === null) return 1;
        if (bv === null) return -1;
        const cmp = av < bv ? -1 : 1;
        return sort.desc ? -cmp : cmp;
      });
  }, [rows, sort]);

  if (rows.length === 0) {
    return <p className="analytics-empty">Nothing in this time window.</p>;
  }

  const shown = top && !showAll ? sorted.slice(0, top) : sorted;

  const toggleSort = (key: string) =>
    setSort((s) => (s?.key === key ? { key, desc: !s.desc } : { key, desc: true }));

  const toggleRow = (index: number) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });

  return (
    <>
      <div className="audit-log-table-wrapper">
        <table className="audit-log-table analytics-table" aria-label={label}>
          <thead>
            <tr>
              {hasDetails && <th className="analytics-expand-cell" aria-label="Details" />}
              {columns.map((c) => (
                <th
                  key={c.key}
                  className={isNumeric(c) ? 'analytics-num' : undefined}
                  aria-sort={
                    sort?.key === c.key ? (sort.desc ? 'descending' : 'ascending') : undefined
                  }
                >
                  <button type="button" className="analytics-sort" onClick={() => toggleSort(c.key)}>
                    {c.label || ' '}
                    {sort?.key === c.key ? (sort.desc ? ' ▾' : ' ▴') : ''}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map(({ row, index }) => (
              <Fragment key={index}>
                <tr
                  className={[
                    row._flag ? 'analytics-row-flag' : '',
                    row._low_sample ? 'analytics-row-low' : '',
                  ].join(' ')}
                >
                  {hasDetails && (
                    <td className="analytics-expand-cell">
                      {row._details && (
                        <button
                          type="button"
                          className="analytics-expand"
                          aria-expanded={expanded.has(index)}
                          aria-label={expanded.has(index) ? 'Hide details' : 'Show details'}
                          onClick={() => toggleRow(index)}
                        >
                          {expanded.has(index) ? '▾' : '▸'}
                        </button>
                      )}
                    </td>
                  )}
                  {columns.map((c, i) => (
                    <td key={c.key} className={isNumeric(c) ? 'analytics-num' : undefined}>
                      <Cell column={c} row={row} />
                      {i === 0 && row._low_sample && (
                        <span className="analytics-low-tag">low sample</span>
                      )}
                    </td>
                  ))}
                </tr>
                {row._details && expanded.has(index) && (
                  <tr className="analytics-details-row">
                    <td colSpan={columns.length + 1}>
                      <MetricTable
                        columns={row._details.columns}
                        rows={row._details.rows}
                        label={`${label}: details`}
                      />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      <div className="analytics-table-footer">
        {top && rows.length > top && (
          <button type="button" className="btn-secondary btn-small" onClick={() => setShowAll((s) => !s)}>
            {showAll ? `Show top ${top}` : `Show all ${rows.length}`}
          </button>
        )}
        {hasLowSample && <span className="field-hint">Greyed-out rows have too few shows or visits to rank.</span>}
      </div>
    </>
  );
}
