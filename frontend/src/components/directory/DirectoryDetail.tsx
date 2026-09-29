import { useEffect, useRef } from 'react';
import type { DirectoryEntry } from '../../types';
import MarkdownContent from '../shared/MarkdownContent';
import StaffPhoto from './StaffPhoto';
import { spinitronUrl } from './directorySearch';

interface DirectoryDetailProps {
  // null when the URL names someone who isn't in the directory
  entry: DirectoryEntry | null;
  isMe: boolean;
  onClose: () => void;
}

// Everything the directory knows about one staff member, in a panel over the
// table. Its URL (/directory/:staffId) can be shared.
const DirectoryDetail = ({ entry, isMe, onClose }: DirectoryDetailProps) => {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [onClose]);

  return (
    <div className="directory-detail-overlay" onClick={onClose}>
      <aside
        className="directory-detail"
        role="dialog"
        aria-modal="true"
        aria-labelledby="directory-detail-name"
        onClick={(event) => event.stopPropagation()}
      >
        <button
          ref={closeRef}
          type="button"
          className="directory-detail-close"
          onClick={onClose}
          aria-label="Close"
        >
          ×
        </button>

        {entry === null ? (
          <p id="directory-detail-name">This person isn't in the staff directory.</p>
        ) : (
          <>
            <div className="directory-detail-heading">
              <StaffPhoto entry={entry} size="medium" />
              <div>
                <h2 id="directory-detail-name">
                  {entry.name}
                  {isMe && <span className="directory-me-tag">You</span>}
                </h2>
                {entry.pronouns && <div className="directory-pronouns">{entry.pronouns}</div>}
              </div>
            </div>

            <dl className="directory-detail-fields">
              <dt>Email</dt>
              <dd><a href={`mailto:${entry.email}`}>{entry.email}</a></dd>

              <dt>Phone</dt>
              <dd>{entry.phone ? <a href={`tel:${entry.phone}`}>{entry.phone}</a> : '—'}</dd>

              <dt>DJ name</dt>
              <dd>
                {entry.dj_name ?? '—'}
                {entry.spinitron_ids.map((personaId, index) => (
                  <a
                    key={personaId}
                    className="directory-spinitron-link"
                    href={spinitronUrl(personaId)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Spinitron profile{entry.spinitron_ids.length > 1 ? ` ${index + 1}` : ''}
                  </a>
                ))}
              </dd>

              <dt>Departments</dt>
              <dd>{entry.departments.length > 0 ? entry.departments.join(', ') : '—'}</dd>

              <dt>Status</dt>
              <dd>{entry.statuses.join(', ')}</dd>

              <dt>Titles and roles</dt>
              <dd>
                {/* A rich text field in Airtable, which returns Markdown */}
                {entry.titles_and_roles ? (
                  <MarkdownContent className="directory-titles" content={entry.titles_and_roles} />
                ) : (
                  '—'
                )}
              </dd>
            </dl>
          </>
        )}
      </aside>
    </div>
  );
};

export default DirectoryDetail;
