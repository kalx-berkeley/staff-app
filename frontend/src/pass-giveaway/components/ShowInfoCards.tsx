import type { ReactNode } from 'react';
import MarkdownContent from '../../common/components/MarkdownContent';
import { formatPhone } from '../../common/utils';
import { formatCalendarDate, formatCalendarDateRange } from '../../common/dateTime';
import { WHEELCHAIR_ACCESSIBLE_LABELS, formatShowRating, isMovieShow } from '../utils';
import type { ShowResponse } from '../types';

const EmailIcon = () => (
  <svg
    width="14"
    height="11"
    viewBox="0 0 14 11"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
    className="email-icon"
  >
    <rect x="0.75" y="0.75" width="12.5" height="9.5" rx="1" stroke="currentColor" strokeWidth="1.5" />
    <path d="M1 1.5l6 4.5 6-4.5" stroke="currentColor" strokeWidth="1.5" />
  </svg>
);

const PhoneIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true" className="phone-icon">
    <path
      d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinejoin="round"
    />
  </svg>
);

const formatDate = (dateStr: string) =>
  formatCalendarDate(dateStr, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

const formatTime = (timeStr: string) => {
  const [hours, minutes] = timeStr.split(':').map(Number);
  return `${hours % 12 || 12}:${String(minutes).padStart(2, '0')} ${hours >= 12 ? 'PM' : 'AM'}`;
};

interface DetailFieldProps {
  label: ReactNode;
  children: ReactNode;
  /** Spans the whole row and sets the value apart, for longer text. */
  wide?: boolean;
}

/** One label/value pair inside a `.detail-fields` `<dl>`. */
const DetailField = ({ label, children, wide }: DetailFieldProps) => (
  <div className={wide ? 'detail-field detail-field--wide' : 'detail-field'}>
    <dt>{label}</dt>
    <dd>{children}</dd>
  </div>
);

interface ShowInfoCardsProps {
  show: ShowResponse;
  /** Note after the "Staff Instructions" label, e.g. who sees them. */
  staffInstructionsNote?: string;
}

/**
 * A show's details and its KALX promotions reps, as two cards side by side
 * (stacked on narrow screens). Shared by the staff and promotions show pages.
 */
const ShowInfoCards = ({ show, staffInstructionsNote }: ShowInfoCardsProps) => {
  const genres = show.genre ?? [];
  const contacts = show.promotions_contacts;

  return (
    <div className={contacts.length > 0 ? 'show-info' : 'show-info show-info--single'}>
      <section className="info-section">
        <h3>Show Information</h3>
        <dl className="detail-fields">
          <DetailField label={show.show_start_date ? 'Dates' : 'Date & Time'}>
            {show.show_start_date ? (
              formatCalendarDateRange(show.show_start_date, show.show_date)
            ) : (
              <>
                {formatDate(show.show_date)}
                {show.show_time && <span className="detail-secondary">{formatTime(show.show_time)}</span>}
              </>
            )}
          </DetailField>

          <DetailField label="Venue">
            {show.venue.name}
            {show.venue.address && <span className="detail-secondary">{show.venue.address}</span>}
          </DetailField>

          <DetailField label={isMovieShow(show) ? 'Movie Rating' : 'Age Restriction'}>
            {formatShowRating(show)}
          </DetailField>

          <DetailField label="Wheelchair Accessible">
            {WHEELCHAIR_ACCESSIBLE_LABELS[show.wheelchair_accessible]}
          </DetailField>

          <DetailField label={genres.length > 1 ? 'Genres' : 'Genre'}>
            {genres.length > 0 ? (
              <span className="detail-tags">
                {genres.map((g) => (
                  <span key={g} className="detail-tag">{g}</span>
                ))}
              </span>
            ) : (
              <span className="detail-empty">None</span>
            )}
          </DetailField>

          {show.planned_close_date && show.planned_close_time && (
            <DetailField label="Planned Close">
              {formatDate(show.planned_close_date)}
              <span className="detail-secondary">
                {formatTime(show.planned_close_time)}
                {show.auto_close && ' · auto-close enabled'}
              </span>
            </DetailField>
          )}

          {show.on_air_description && (
            <DetailField label="On-Air Description" wide>
              <MarkdownContent content={show.on_air_description} />
            </DetailField>
          )}

          {show.caller_special_instructions && (
            <DetailField label="Caller Special Instructions" wide>
              <MarkdownContent content={show.caller_special_instructions} />
            </DetailField>
          )}

          {show.staff_instructions && (
            <DetailField
              label={
                <>
                  Staff Instructions
                  {staffInstructionsNote && <span className="detail-label-note"> {staffInstructionsNote}</span>}
                </>
              }
              wide
            >
              <MarkdownContent content={show.staff_instructions} />
            </DetailField>
          )}
        </dl>
      </section>

      {contacts.length > 0 && (
        <section className="info-section">
          <h3>KALX Promotions Rep{contacts.length > 1 ? 's' : ''}</h3>
          <ul className="contact-list">
            {contacts.map((contact) => (
              <li key={contact.email} className="contact-card">
                <span className="contact-name">{contact.name}</span>
                {contact.phone && (
                  <a href={`tel:${contact.phone}`} className="contact-line">
                    <PhoneIcon />
                    {formatPhone(contact.phone)}
                  </a>
                )}
                <a href={`mailto:${contact.email}`} className="contact-line email-link">
                  <EmailIcon />
                  {contact.email}
                </a>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
};

export default ShowInfoCards;
