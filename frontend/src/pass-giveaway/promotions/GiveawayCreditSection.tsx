import { useCallback, useEffect, useState } from 'react';
import { adminAPI } from '../api';
import { IdentityPicker } from '../components';
import type { GiveawayCreditItem, Identity } from '../types';
import type { APIError } from '../../common/types';
import { formatCalendarDate, formatPacific } from '../../common/dateTime';

const errorText = (err: unknown, fallback: string) => {
  const detail = (err as APIError).detail;
  return typeof detail === 'string' ? detail : fallback;
};

const DAY_CHOICES = [30, 90, 365];

/**
 * Promotions → Admin: giveaways and who they're credited to, with a way to
 * re-credit any of them (decision 28 of
 * docs/pass-giveaway/specs/spinitron-identity/plan.md). A giveaway made
 * while no one was on air (automation, a placeholder persona, a gap) is "Unattributed",
 * so the list starts with only those.
 */
const GiveawayCreditSection = () => {
  const [unattributedOnly, setUnattributedOnly] = useState(true);
  const [days, setDays] = useState(90);
  const [rows, setRows] = useState<GiveawayCreditItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [identities, setIdentities] = useState<Identity[]>([]);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [picked, setPicked] = useState<Identity | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setRows(await adminAPI.getGiveaways(unattributedOnly, days));
    } catch (err) {
      setError(errorText(err, 'Failed to load giveaways'));
    } finally {
      setLoading(false);
    }
  }, [unattributedOnly, days]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    adminAPI.getCreditIdentities().then(setIdentities).catch(() => {});
  }, []);

  const startEditing = (row: GiveawayCreditItem) => {
    setEditingId(row.pass_id);
    setSaveError(null);
    setPicked(
      identities.find(
        (i) =>
          (row.specialty_show_id !== null && i.specialty_show_id === row.specialty_show_id) ||
          (row.specialty_show_id === null &&
            row.persona_id !== null &&
            i.persona_id === row.persona_id),
      ) ?? null,
    );
  };

  const save = async (row: GiveawayCreditItem) => {
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await adminAPI.recreditGiveaway(row.pass_id, picked);
      setEditingId(null);
      // Still listed until the next load, so the change is visible
      setRows((prev) => prev.map((r) => (r.pass_id === row.pass_id ? updated : r)));
    } catch (err) {
      setSaveError(errorText(err, 'Failed to re-credit the giveaway'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="admin-section">
      <h3>Giveaway Credit</h3>
      <p className="field-hint">
        Who each on-air giveaway is credited to. The DJ pages credit whoever the Spinitron
        schedule has on air; a giveaway made while no one was (automation, a placeholder persona, a gap)
        is unattributed. Re-credit a giveaway to a DJ or a show here; each change is
        recorded in the audit log.
      </p>
      <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={unattributedOnly}
            onChange={(e) => setUnattributedOnly(e.target.checked)}
          />
          Unattributed only
        </label>
        <label>
          Given away in the last{' '}
          <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
            {DAY_CHOICES.map((d) => (
              <option key={d} value={d}>
                {d} days
              </option>
            ))}
          </select>
        </label>
      </div>

      {loading ? (
        <p>Loading…</p>
      ) : error ? (
        <div className="error-message">{error}</div>
      ) : rows.length === 0 ? (
        <p className="field-hint">
          {unattributedOnly ? 'No unattributed giveaways.' : 'No giveaways.'}
        </p>
      ) : (
        <div className="scrollable-table-wrapper">
          <table className="audit-log-table">
            <thead>
              <tr>
                <th>Show</th>
                <th>Given Away (PT)</th>
                <th>Winner</th>
                <th>Credited To</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.pass_id}>
                  <td>
                    <a href={`/pass-giveaway/promotions/shows/${row.show_id}`}>{row.event_name}</a>
                    <div className="field-hint">
                      {row.venue_name} · {formatCalendarDate(row.show_date)}
                    </div>
                  </td>
                  <td className="audit-log-time">
                    {row.given_away_at ? formatPacific(row.given_away_at) : '—'}
                  </td>
                  <td>{row.recipient_name ?? '—'}</td>
                  <td>
                    {editingId === row.pass_id ? (
                      <IdentityPicker
                        id={`credit-${row.pass_id}`}
                        aria-label={`Credit the ${row.event_name} giveaway to`}
                        options={identities}
                        value={picked}
                        onChange={setPicked}
                        placeholder="DJ or show (blank for unattributed)"
                        disabled={saving}
                      />
                    ) : (
                      row.credited_to
                    )}
                    {editingId === row.pass_id && saveError && (
                      <div className="error-message">{saveError}</div>
                    )}
                  </td>
                  <td>
                    {editingId === row.pass_id ? (
                      <div className="show-row-actions">
                        <button
                          type="button"
                          className="btn-primary btn-small"
                          onClick={() => save(row)}
                          disabled={saving}
                        >
                          {saving ? 'Saving…' : 'Save'}
                        </button>
                        <button
                          type="button"
                          className="btn-secondary btn-small"
                          onClick={() => setEditingId(null)}
                          disabled={saving}
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        className="btn-secondary btn-small"
                        onClick={() => startEditing(row)}
                        disabled={editingId !== null}
                        aria-label={`Re-credit the ${row.event_name} giveaway`}
                      >
                        Re-credit
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
};

export default GiveawayCreditSection;
