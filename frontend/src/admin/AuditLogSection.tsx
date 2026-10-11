import { useState, type KeyboardEvent } from 'react';
import type { APIError } from '../common/types';
import { adminAPI } from './api';
import type { AuditLogItem } from './types';
import { toPacificDateInputValue } from './utils';

const PAGE_SIZE = 50;

const defaultSince = (): string => {
  const d = new Date();
  d.setDate(d.getDate() - 30);
  return toPacificDateInputValue(d);
};

// The audit log of every sub-site, filtered by date, event type and actor.
export default function AuditLogSection() {
  const [entries, setEntries] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [eventType, setEventType] = useState('');
  const [actorEmail, setActorEmail] = useState('');
  const [since, setSince] = useState(defaultSince);
  const [until, setUntil] = useState(() => toPacificDateInputValue(new Date()));

  const load = async (reset: boolean) => {
    setLoading(true);
    setError(null);
    const from = reset ? 0 : offset;
    try {
      const page = await adminAPI.getAuditLog({
        event_type: eventType || undefined,
        actor_email: actorEmail || undefined,
        since: since || undefined,
        until: until || undefined,
        limit: PAGE_SIZE,
        offset: from,
      });
      setEntries((prev) => (reset ? page : [...prev, ...page]));
      setOffset(from + page.length);
      setHasMore(page.length === PAGE_SIZE);
    } catch (err) {
      const detail = (err as APIError).detail;
      setError(typeof detail === 'string' ? detail : 'Failed to load audit log');
    } finally {
      setLoading(false);
    }
  };

  const loadOnEnter = (e: KeyboardEvent) => {
    if (e.key === 'Enter') load(true);
  };

  return (
    <section className="admin-section">
      <h2>Audit Log</h2>
      <div className="audit-log-filters">
        <label className="audit-log-filter-label">
          From
          <input type="date" value={since} onChange={(e) => setSince(e.target.value)} />
        </label>
        <label className="audit-log-filter-label">
          To
          <input type="date" value={until} onChange={(e) => setUntil(e.target.value)} />
        </label>
        <input
          type="text"
          placeholder="Event type"
          aria-label="Event type"
          value={eventType}
          onChange={(e) => setEventType(e.target.value)}
          onKeyDown={loadOnEnter}
        />
        <input
          type="text"
          placeholder="Actor email"
          aria-label="Actor email"
          value={actorEmail}
          onChange={(e) => setActorEmail(e.target.value)}
          onKeyDown={loadOnEnter}
        />
        <button className="btn-primary" onClick={() => load(true)} disabled={loading}>
          {loading && entries.length === 0 ? 'Loading…' : 'Load'}
        </button>
      </div>
      {error && <div className="error-message">{error}</div>}
      {entries.length === 0 && !loading && !error && (
        <p className="field-help">Use the filters above and click Load to fetch entries.</p>
      )}
      {entries.length > 0 && (
        <>
          <div className="audit-log-table-wrapper">
            <table className="audit-log-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Event</th>
                  <th>Actor</th>
                  <th>Role</th>
                  <th>Entity</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <tr key={entry.id}>
                    <td className="audit-log-time">
                      {new Date(entry.occurred_at).toLocaleString('en-US', {
                        timeZone: 'America/Los_Angeles',
                      })}
                    </td>
                    <td>
                      <code>{entry.event_type}</code>
                    </td>
                    <td>{entry.actor_email ?? '—'}</td>
                    <td>{entry.actor_role ?? '—'}</td>
                    <td>
                      {entry.entity_type
                        ? `${entry.entity_type}${entry.entity_id != null ? ` #${entry.entity_id}` : ''}`
                        : '—'}
                    </td>
                    <td className="audit-log-details">
                      {entry.details ? (
                        <details>
                          <summary>{JSON.stringify(entry.details)}</summary>
                          <pre>{JSON.stringify(entry.details, null, 2)}</pre>
                        </details>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {hasMore && (
            <button className="btn-secondary" onClick={() => load(false)} disabled={loading}>
              {loading ? 'Loading…' : 'Load More'}
            </button>
          )}
        </>
      )}
    </section>
  );
}
