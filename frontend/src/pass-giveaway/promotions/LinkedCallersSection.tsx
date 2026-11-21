import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';
import { callersAPI } from '../api';
import type {
  CallerLinkPreview,
  CallerPhone,
  CallerSuggestion,
  CommonCallerName,
  LinkedCaller,
} from '../types';
import type { APIError } from '../../common/types';
import { formatCalendarDate, formatPacific } from '../../common/dateTime';
import { formatPhone } from '../../common/utils';

const errorText = (err: unknown, fallback: string) => {
  const detail = (err as APIError).detail;
  return typeof detail === 'string' ? detail : fallback;
};

const DATE_ONLY = { month: 'short', day: 'numeric', year: 'numeric' } as const;

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`;

/** One phone number: its number, the names it won under and its wins. */
function PhoneLabel({ phone }: { phone: CallerPhone }) {
  return (
    <>
      <strong>{formatPhone(phone.phone)}</strong>
      {phone.names.length > 0 && <> · {phone.names.join(', ')}</>}
      {' · '}
      {plural(phone.wins, 'win')}
      {phone.last_won_at && <>, last {formatPacific(phone.last_won_at, DATE_ONLY)}</>}
    </>
  );
}

interface PendingLink {
  phones: string[];
  preview: CallerLinkPreview;
  note: string;
}

/**
 * Promotions → Admin: link on-air winners' phone numbers that belong to one
 * person, so venue win frequency limits check every one of them
 * (docs/pass-giveaway/specs/linked-callers/plan.md). KALX Staff Analytics
 * links here with ?caller=<name>#linked-callers.
 */
const LinkedCallersSection = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const { hash } = useLocation();
  const callerFilter = searchParams.get('caller') ?? '';
  const sectionRef = useRef<HTMLElement>(null);
  const scrolled = useRef(false);

  const [showResolved, setShowResolved] = useState(false);
  const [suggestions, setSuggestions] = useState<CallerSuggestion[]>([]);
  const [callers, setCallers] = useState<LinkedCaller[]>([]);
  const [commonNames, setCommonNames] = useState<CommonCallerName[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Suggestion key → its checked numbers
  const [checked, setChecked] = useState<Record<string, string[]>>({});
  const [pending, setPending] = useState<PendingLink | null>(null);

  const [query, setQuery] = useState('');
  const [results, setResults] = useState<CallerPhone[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [picked, setPicked] = useState<string[]>([]);

  const [editingNote, setEditingNote] = useState<{ id: number; text: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, c, n] = await Promise.all([
        callersAPI.getSuggestions(showResolved, callerFilter || undefined),
        callersAPI.list(),
        callersAPI.getCommonNames(),
      ]);
      setSuggestions(s);
      setCallers(c);
      setCommonNames(n);
      setChecked(Object.fromEntries(s.map((g) => [g.key, g.phones.map((p) => p.phone)])));
    } catch (err) {
      setError(errorText(err, 'Failed to load linked callers'));
    } finally {
      setLoading(false);
    }
  }, [showResolved, callerFilter]);

  useEffect(() => {
    load();
  }, [load]);

  // Analytics links here; scroll once the section has its content
  useEffect(() => {
    if (!loading && hash === '#linked-callers' && !scrolled.current) {
      scrolled.current = true;
      sectionRef.current?.scrollIntoView?.({ block: 'start' });
    }
  }, [loading, hash]);

  /** Run a change, then reload everything it may have touched. */
  const act = async (fn: () => Promise<unknown>, fallback: string) => {
    setBusy(true);
    setActionError(null);
    try {
      await fn();
      await load();
      return true;
    } catch (err) {
      setActionError(errorText(err, fallback));
      return false;
    } finally {
      setBusy(false);
    }
  };

  const startLink = async (phones: string[]) => {
    setActionError(null);
    try {
      const preview = await callersAPI.preview(phones);
      setPending({ phones, preview, note: '' });
    } catch (err) {
      setActionError(errorText(err, 'Failed to check those numbers'));
    }
  };

  const confirmLink = async () => {
    if (!pending) return;
    const ok = await act(() => callersAPI.link(pending.phones, pending.note), 'Failed to link');
    if (ok) {
      setPending(null);
      setPicked([]);
      setResults(null);
      setQuery('');
    }
  };

  const runSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim().length < 2) return;
    setSearching(true);
    setActionError(null);
    try {
      setResults(await callersAPI.search(query.trim()));
    } catch (err) {
      setActionError(errorText(err, 'Search failed'));
    } finally {
      setSearching(false);
    }
  };

  const toggle = (list: string[], phone: string) =>
    list.includes(phone) ? list.filter((p) => p !== phone) : [...list, phone];

  const clearFilter = () => {
    const next = new URLSearchParams(searchParams);
    next.delete('caller');
    setSearchParams(next);
  };

  const filteredCallerIds = new Set(
    suggestions.flatMap((g) => g.phones.map((p) => p.caller_id)).filter((id) => id !== null)
  );
  const shownCallers = callerFilter ? callers.filter((c) => filteredCallerIds.has(c.id)) : callers;

  const confirmation = pending && (
    <div className="linked-callers-confirm" role="dialog" aria-label="Confirm linking">
      <p>
        {pending.preview.caller_ids.length > 1
          ? `This merges ${pending.preview.caller_ids.length} linked callers. `
          : pending.preview.caller_ids.length === 1
            ? 'This adds to an existing linked caller. '
            : ''}
        These numbers will be one caller, and a venue's win frequency limit will check wins on all
        of them:
      </p>
      <ul>
        {pending.preview.phones.map((p) => (
          <li key={p}>{formatPhone(p)}</li>
        ))}
      </ul>
      <label htmlFor="linked-callers-note">Note (optional)</label>
      <input
        id="linked-callers-note"
        type="text"
        value={pending.note}
        placeholder="Why they're the same person, e.g. same email"
        onChange={(e) => setPending({ ...pending, note: e.target.value })}
      />
      <div className="linked-callers-actions">
        <button className="btn-primary btn-small" onClick={confirmLink} disabled={busy}>
          {busy ? 'Linking…' : 'Link these numbers'}
        </button>
        <button
          className="btn-secondary btn-small"
          onClick={() => setPending(null)}
          disabled={busy}
        >
          Cancel
        </button>
      </div>
    </div>
  );

  return (
    <section className="admin-section" id="linked-callers" ref={sectionRef}>
      <h3>Linked Callers</h3>
      <p className="field-hint">
        Some callers give a different phone number each time they win. Link the numbers of one
        person here, and a venue's win frequency limit checks the wins on all of them. Suggestions
        are on-air winners with similar names and different numbers. Link the ones that are one
        person, dismiss the ones that aren't, and mark names too common to be worth suggesting.
        Every change is recorded in the audit log.
      </p>

      {callerFilter && (
        <p className="linked-callers-filter">
          Showing “{callerFilter}”.{' '}
          <button type="button" className="btn-link" onClick={clearFilter}>
            Show everyone
          </button>
        </p>
      )}

      {actionError && <div className="error-message">{actionError}</div>}

      <h4>Suggestions</h4>
      {!callerFilter && (
        <label className="linked-callers-toggle">
          <input
            type="checkbox"
            checked={showResolved}
            onChange={(e) => setShowResolved(e.target.checked)}
          />
          Show resolved (linked, dismissed and common names)
        </label>
      )}
      {loading ? (
        <p>Loading…</p>
      ) : error ? (
        <div className="error-message">{error}</div>
      ) : suggestions.length === 0 ? (
        <p className="field-hint">
          {callerFilter ? 'No similar names with different numbers.' : 'Nothing to review.'}
        </p>
      ) : (
        suggestions.map((g) => {
          const selected = checked[g.key] ?? [];
          const isPending = pending && pending.phones.join() === selected.join();
          return (
            <div key={g.key} className={`linked-callers-group${g.flagged ? ' flagged' : ''}`}>
              <div className="linked-callers-group-header">
                <strong>{g.name}</strong>
                <span className={`status-badge linked-callers-status-${g.status}`}>
                  {g.status_label}
                </span>
                {g.flagged && (
                  <span className="linked-callers-flag">Would have broken a venue's limit</span>
                )}
              </div>
              {g.spellings.length > 1 && (
                <p className="field-hint">Spellings: {g.spellings.join(', ')}</p>
              )}
              <fieldset className="linked-callers-phones">
                <legend>Phone numbers</legend>
                {g.phones.map((p) => (
                  <label key={p.phone}>
                    <input
                      type="checkbox"
                      checked={selected.includes(p.phone)}
                      onChange={() =>
                        setChecked({ ...checked, [g.key]: toggle(selected, p.phone) })
                      }
                    />
                    <span>
                      <PhoneLabel phone={p} />
                      {p.caller_id !== null && <> · linked</>}
                    </span>
                  </label>
                ))}
              </fieldset>
              <details>
                <summary>{plural(g.wins.length, 'win')}</summary>
                <div className="scrollable-table-wrapper">
                  <table className="audit-log-table">
                    <thead>
                      <tr>
                        <th>Won</th>
                        <th>Name</th>
                        <th>Phone</th>
                        <th>Email</th>
                        <th>Show</th>
                        <th>Show date</th>
                        <th>Venue</th>
                      </tr>
                    </thead>
                    <tbody>
                      {g.wins.map((w) => (
                        <tr key={w.pass_id}>
                          <td className="audit-log-time">{formatPacific(w.won_at, DATE_ONLY)}</td>
                          <td>{w.name}</td>
                          <td>{formatPhone(w.phone)}</td>
                          <td>{w.email ?? ''}</td>
                          <td>
                            <a href={`/pass-giveaway/promotions/shows/${w.show_id}`}>{w.show}</a>
                          </td>
                          <td>{w.show_date ? formatCalendarDate(w.show_date) : ''}</td>
                          <td>{w.venue}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
              <div className="linked-callers-actions">
                <button
                  className="btn-primary btn-small"
                  disabled={busy || selected.length < 2 || g.status === 'linked'}
                  onClick={() => startLink(selected)}
                >
                  Link checked numbers
                </button>
                {g.status === 'dismissed' ? (
                  <button
                    className="btn-secondary btn-small"
                    disabled={busy}
                    onClick={() =>
                      act(
                        () => callersAPI.undoDismissal(g.phones.map((p) => p.phone)),
                        'Failed to undo'
                      )
                    }
                  >
                    Undo “not the same person”
                  </button>
                ) : (
                  g.status !== 'linked' && (
                    <button
                      className="btn-secondary btn-small"
                      disabled={busy}
                      onClick={() =>
                        act(
                          () => callersAPI.dismiss(g.phones.map((p) => p.phone)),
                          'Failed to dismiss'
                        )
                      }
                    >
                      Not the same person
                    </button>
                  )
                )}
                {g.common_names.length > 0 ? (
                  g.common_names.map((n) => (
                    <button
                      key={n}
                      className="btn-secondary btn-small"
                      disabled={busy}
                      onClick={() => act(() => callersAPI.unmarkCommon(n), 'Failed to unmark')}
                    >
                      “{n}” isn't too common
                    </button>
                  ))
                ) : (
                  <button
                    className="btn-secondary btn-small"
                    disabled={busy}
                    title="Stop suggesting this name, however its numbers are spelled"
                    onClick={() => act(() => callersAPI.markCommon(g.name), 'Failed to mark')}
                  >
                    Name too common
                  </button>
                )}
              </div>
              {isPending && confirmation}
            </div>
          );
        })
      )}

      <h4>Link by hand</h4>
      <p className="field-hint">
        For names the suggestions miss, such as a nickname. Search by name or phone number, check
        the numbers that are one person, and link them.
      </p>
      <form className="linked-callers-search" onSubmit={runSearch} role="search">
        <label htmlFor="linked-callers-query" className="visually-hidden">
          Name or phone number
        </label>
        <input
          id="linked-callers-query"
          type="search"
          value={query}
          placeholder="Name or phone number"
          onChange={(e) => setQuery(e.target.value)}
        />
        <button type="submit" className="btn-secondary btn-small" disabled={searching}>
          {searching ? 'Searching…' : 'Search'}
        </button>
      </form>
      {results !== null &&
        (results.length === 0 ? (
          <p className="field-hint">No winners match.</p>
        ) : (
          <fieldset className="linked-callers-phones">
            <legend>Results</legend>
            {results.map((p) => (
              <label key={p.phone}>
                <input
                  type="checkbox"
                  checked={picked.includes(p.phone)}
                  onChange={() => setPicked(toggle(picked, p.phone))}
                />
                <span>
                  <PhoneLabel phone={p} />
                  {p.caller_id !== null && <> · linked</>}
                </span>
              </label>
            ))}
          </fieldset>
        ))}
      {picked.length > 0 && (
        <div className="linked-callers-actions">
          <span>{plural(picked.length, 'number')} checked</span>
          <button
            className="btn-primary btn-small"
            disabled={busy || picked.length < 2}
            onClick={() => startLink(picked)}
          >
            Link checked numbers
          </button>
          <button className="btn-secondary btn-small" onClick={() => setPicked([])}>
            Clear
          </button>
        </div>
      )}
      {pending && pending.phones.join() === picked.join() && confirmation}

      <h4>Linked callers</h4>
      {loading ? null : shownCallers.length === 0 ? (
        <p className="field-hint">No linked callers{callerFilter ? ' for this name' : ''}.</p>
      ) : (
        shownCallers.map((c) => (
          <div key={c.id} className="linked-callers-group">
            <ul className="linked-callers-caller-phones">
              {c.phones.map((p) => (
                <li key={p.phone}>
                  <span>
                    <PhoneLabel phone={p} />
                    {p.wins === 0 && (
                      <span className="linked-callers-stale">
                        {' '}
                        {formatPhone(p.phone)} is linked but has no wins any more
                      </span>
                    )}
                  </span>
                  <button
                    className="btn-secondary btn-small"
                    disabled={busy}
                    onClick={() =>
                      act(() => callersAPI.unlinkPhone(c.id, p.phone), 'Failed to remove')
                    }
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
            {editingNote?.id === c.id ? (
              <div className="linked-callers-actions">
                <label htmlFor={`caller-note-${c.id}`} className="visually-hidden">
                  Note
                </label>
                <input
                  id={`caller-note-${c.id}`}
                  type="text"
                  value={editingNote.text}
                  onChange={(e) => setEditingNote({ id: c.id, text: e.target.value })}
                />
                <button
                  className="btn-primary btn-small"
                  disabled={busy}
                  onClick={async () => {
                    if (
                      await act(
                        () => callersAPI.updateNote(c.id, editingNote.text),
                        'Failed to save'
                      )
                    ) {
                      setEditingNote(null);
                    }
                  }}
                >
                  Save
                </button>
                <button className="btn-secondary btn-small" onClick={() => setEditingNote(null)}>
                  Cancel
                </button>
              </div>
            ) : (
              <p className="linked-callers-note">
                {c.note ? (
                  <span className="linked-callers-note-text">{c.note}</span>
                ) : (
                  <span className="field-hint">No note.</span>
                )}{' '}
                <button
                  type="button"
                  className="btn-link"
                  onClick={() => setEditingNote({ id: c.id, text: c.note ?? '' })}
                >
                  {c.note ? 'Edit note' : 'Add a note'}
                </button>
              </p>
            )}
            <p className="field-hint">
              Linked {formatPacific(c.created_at, DATE_ONLY)}.{' '}
              <button
                type="button"
                className="btn-link"
                disabled={busy}
                onClick={() => {
                  if (
                    window.confirm(
                      'Unlink all of these numbers? Each will be checked on its own again.'
                    )
                  ) {
                    act(() => callersAPI.unlink(c.id), 'Failed to unlink');
                  }
                }}
              >
                Unlink all
              </button>
            </p>
          </div>
        ))
      )}

      <h4>Names too common to suggest</h4>
      {loading ? null : commonNames.length === 0 ? (
        <p className="field-hint">None.</p>
      ) : (
        <ul className="linked-callers-common">
          {commonNames.map((n) => (
            <li key={n.name}>
              {n.name}{' '}
              <button
                type="button"
                className="btn-link"
                disabled={busy}
                onClick={() => act(() => callersAPI.unmarkCommon(n.name), 'Failed to unmark')}
              >
                Unmark
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
};

export default LinkedCallersSection;
