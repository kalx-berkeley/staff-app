import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { PRESETS, readWindow } from './timeWindow';
import type { AnalyticsWindow } from './types';
import { formatValue } from './format';

const CUSTOM = 'custom';

// The shared time-window control: a preset, or a custom from–to range. The
// choice lives in the URL, so it's kept between tabs and in shared links.
export default function WindowPicker({ resolved }: { resolved: AnalyticsWindow | null }) {
  const [search, setSearch] = useSearchParams();
  const current = readWindow(search);
  const [mode, setMode] = useState(current.from ? CUSTOM : current.preset!);
  const [from, setFrom] = useState(current.from ?? resolved?.start ?? '');
  const [to, setTo] = useState(current.to ?? resolved?.end ?? '');

  const update = (apply: (next: URLSearchParams) => void) => {
    const next = new URLSearchParams(search);
    next.delete('preset');
    next.delete('from');
    next.delete('to');
    apply(next);
    setSearch(next);
  };

  const choose = (value: string) => {
    setMode(value);
    if (value === CUSTOM) {
      setFrom(resolved?.start ?? '');
      setTo(resolved?.end ?? '');
      return;
    }
    update((next) => next.set('preset', value));
  };

  const applyRange = (e: React.FormEvent) => {
    e.preventDefault();
    if (from && to) {
      update((next) => {
        next.set('from', from <= to ? from : to);
        next.set('to', from <= to ? to : from);
      });
    }
  };

  return (
    <form className="analytics-window" onSubmit={applyRange}>
      <label>
        <span>Time window</span>
        <select value={mode} onChange={(e) => choose(e.target.value)}>
          {PRESETS.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label}
            </option>
          ))}
          <option value={CUSTOM}>Custom range…</option>
        </select>
      </label>
      {mode === CUSTOM && (
        <>
          <label>
            <span>From</span>
            <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} required />
          </label>
          <label>
            <span>To</span>
            <input type="date" value={to} onChange={(e) => setTo(e.target.value)} required />
          </label>
          <button type="submit" className="btn-primary btn-small">
            Apply
          </button>
        </>
      )}
      {resolved && (
        <span className="analytics-window-dates">
          {formatValue(resolved.start, 'date')} – {formatValue(resolved.end, 'date')}
        </span>
      )}
    </form>
  );
}
