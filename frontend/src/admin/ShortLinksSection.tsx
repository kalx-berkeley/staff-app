import { useEffect, useState } from 'react';
import type { APIError } from '../common/types';
import { adminAPI } from './api';
import type { ShortLink, ShortLinkRequest } from './types';

const EMPTY_FORM: ShortLinkRequest = { slug: '', target_url: '', note: '' };

const errorDetail = (err: unknown, fallback: string): string => {
  const detail = (err as APIError).detail;
  return typeof detail === 'string' ? detail : fallback;
};

const shortUrl = (slug: string) => `${window.location.origin}/go/${slug}`;

const formatUpdated = (iso: string) =>
  new Date(iso).toLocaleString('en-US', {
    timeZone: 'America/Los_Angeles',
    dateStyle: 'medium',
    timeStyle: 'short',
  });

const matches = (link: ShortLink, filter: string) => {
  const needle = filter.trim().toLowerCase();
  return (
    !needle ||
    [link.slug, link.target_url, link.note ?? ''].some((text) =>
      text.toLowerCase().includes(needle)
    )
  );
};

const bySlug = (a: ShortLink, b: ShortLink) => a.slug.localeCompare(b.slug);

// Site admins only: the /go/<slug> short links, which redirect signed-in
// staff to their target. Slugs ignore case and are stored lowercase.
export default function ShortLinksSection() {
  const [links, setLinks] = useState<ShortLink[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [filter, setFilter] = useState('');
  const [form, setForm] = useState<ShortLinkRequest>(EMPTY_FORM);
  const [createError, setCreateError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<ShortLinkRequest>(EMPTY_FORM);
  const [rowError, setRowError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [copiedId, setCopiedId] = useState<number | null>(null);

  useEffect(() => {
    adminAPI
      .listShortLinks()
      .then(setLinks)
      .catch((err) => setLoadError(errorDetail(err, 'Failed to load short links')));
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    setCreateError(null);
    try {
      const link = await adminAPI.createShortLink({ ...form, note: form.note || null });
      setLinks((prev) => [...(prev ?? []), link].sort(bySlug));
      setForm(EMPTY_FORM);
    } catch (err) {
      setCreateError(errorDetail(err, 'Failed to create the short link'));
    } finally {
      setCreating(false);
    }
  };

  const startEdit = (link: ShortLink) => {
    setEditingId(link.id);
    setEditForm({ slug: link.slug, target_url: link.target_url, note: link.note ?? '' });
    setRowError(null);
  };

  const handleSave = async (id: number) => {
    setSaving(true);
    setRowError(null);
    try {
      const updated = await adminAPI.updateShortLink(id, {
        ...editForm,
        note: editForm.note || null,
      });
      setLinks((prev) => (prev ?? []).map((l) => (l.id === id ? updated : l)).sort(bySlug));
      setEditingId(null);
    } catch (err) {
      setRowError(errorDetail(err, 'Failed to save the short link'));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (link: ShortLink) => {
    if (!window.confirm(`Delete /go/${link.slug}? Anyone using it will get "not found".`)) {
      return;
    }
    setRowError(null);
    try {
      await adminAPI.deleteShortLink(link.id);
      setLinks((prev) => (prev ?? []).filter((l) => l.id !== link.id));
      if (editingId === link.id) setEditingId(null);
    } catch (err) {
      setRowError(errorDetail(err, 'Failed to delete the short link'));
    }
  };

  const handleCopy = async (link: ShortLink) => {
    try {
      await navigator.clipboard.writeText(shortUrl(link.slug));
      setCopiedId(link.id);
    } catch {
      // clipboard API unavailable
    }
  };

  const shown = (links ?? []).filter((link) => matches(link, filter));

  return (
    <section className="admin-section">
      <h2>Short Links</h2>
      <p className="field-hint">
        Each link at <code>/go/&lt;slug&gt;</code> sends signed-in KALX staff to its target. Slugs
        ignore case. Only staff can follow them, so don't use them for links meant for the public.
      </p>

      <form className="short-links-form" onSubmit={handleCreate}>
        <input
          type="text"
          className="short-links-slug"
          aria-label="Slug"
          placeholder="slug"
          value={form.slug}
          onChange={(e) => setForm({ ...form, slug: e.target.value })}
          required
          maxLength={64}
        />
        <input
          type="url"
          className="short-links-wide"
          aria-label="Target URL"
          placeholder="https://…"
          value={form.target_url}
          onChange={(e) => setForm({ ...form, target_url: e.target.value })}
          required
          maxLength={2048}
        />
        <input
          type="text"
          className="short-links-wide"
          aria-label="Note"
          placeholder="Note (optional)"
          value={form.note ?? ''}
          onChange={(e) => setForm({ ...form, note: e.target.value })}
        />
        <button type="submit" className="btn-primary" disabled={creating}>
          {creating ? 'Creating…' : 'Create'}
        </button>
      </form>
      {createError && <div className="error-message">{createError}</div>}

      {loadError ? (
        <div className="error-message">{loadError}</div>
      ) : links === null ? (
        <p>Loading short links…</p>
      ) : links.length === 0 ? (
        <p>No short links yet.</p>
      ) : (
        <>
          <div className="audit-log-filters">
            <input
              type="search"
              aria-label="Filter short links"
              placeholder="Filter by slug, target or note"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </div>
          {rowError && <div className="error-message">{rowError}</div>}
          <div className="audit-log-table-wrapper">
            <table className="audit-log-table short-links-table">
              <thead>
                <tr>
                  <th>Slug</th>
                  <th>Target</th>
                  <th>Note</th>
                  <th>Created By</th>
                  <th>Updated</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((link) =>
                  editingId === link.id ? (
                    <tr key={link.id}>
                      <td>
                        <input
                          type="text"
                          aria-label="Edit slug"
                          value={editForm.slug}
                          onChange={(e) => setEditForm({ ...editForm, slug: e.target.value })}
                          maxLength={64}
                        />
                      </td>
                      <td>
                        <input
                          type="url"
                          aria-label="Edit target URL"
                          value={editForm.target_url}
                          onChange={(e) => setEditForm({ ...editForm, target_url: e.target.value })}
                          maxLength={2048}
                        />
                      </td>
                      <td>
                        <input
                          type="text"
                          aria-label="Edit note"
                          value={editForm.note ?? ''}
                          onChange={(e) => setEditForm({ ...editForm, note: e.target.value })}
                        />
                      </td>
                      <td>{link.created_by_email}</td>
                      <td className="audit-log-time">{formatUpdated(link.updated_at)}</td>
                      <td className="short-links-actions">
                        <button
                          className="btn-primary btn-small"
                          onClick={() => handleSave(link.id)}
                          disabled={saving}
                        >
                          {saving ? 'Saving…' : 'Save'}
                        </button>
                        <button
                          className="btn-secondary btn-small"
                          onClick={() => setEditingId(null)}
                          disabled={saving}
                        >
                          Cancel
                        </button>
                      </td>
                    </tr>
                  ) : (
                    <tr key={link.id}>
                      <td>
                        <code>/go/{link.slug}</code>
                      </td>
                      <td className="short-links-target">
                        <a href={link.target_url} target="_blank" rel="noopener noreferrer">
                          {link.target_url}
                        </a>
                      </td>
                      <td>{link.note}</td>
                      <td>{link.created_by_email}</td>
                      <td className="audit-log-time">{formatUpdated(link.updated_at)}</td>
                      <td className="short-links-actions">
                        <button
                          className="btn-secondary btn-small"
                          onClick={() => handleCopy(link)}
                          aria-label={`Copy /go/${link.slug}`}
                        >
                          {copiedId === link.id ? 'Copied' : 'Copy'}
                        </button>
                        <button
                          className="btn-secondary btn-small"
                          onClick={() => startEdit(link)}
                          aria-label={`Edit /go/${link.slug}`}
                        >
                          Edit
                        </button>
                        <button
                          className="btn-danger btn-small"
                          onClick={() => handleDelete(link)}
                          aria-label={`Delete /go/${link.slug}`}
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  )
                )}
              </tbody>
            </table>
          </div>
          {shown.length === 0 && <p>No short links match “{filter}”.</p>}
        </>
      )}
    </section>
  );
}
