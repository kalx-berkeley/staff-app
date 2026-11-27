import type { ShowResponse } from '../types';
import {
  calendarFile,
  calendarFilename,
  DEFAULT_EVENT_DURATION_HOURS,
  googleCalendarUrl,
} from './calendarExport';

interface AddToCalendarProps {
  show: ShowResponse;
}

const GoogleCalendarIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <rect x="3" y="4" width="18" height="17" rx="2" fill="#fff" stroke="#5f6368" strokeWidth="1.5" />
    <path d="M3 9h18" stroke="#4285f4" strokeWidth="3" />
    <path d="M7 2v4M17 2v4" stroke="#34a853" strokeWidth="2" strokeLinecap="round" />
    <rect x="6" y="12" width="4" height="4" rx="1" fill="#fbbc04" />
    <rect x="14" y="12" width="4" height="4" rx="1" fill="#ea4335" />
  </svg>
);

const IcsIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <path d="M5 2.75h9l5 5v13.5H5z" fill="#fff" stroke="#5f6368" strokeWidth="1.5" strokeLinejoin="round" />
    <path d="M14 2.75v5h5" fill="none" stroke="#5f6368" strokeWidth="1.5" strokeLinejoin="round" />
    <text x="12" y="16" textAnchor="middle" fill="#34495e" fontSize="5.5" fontWeight="700">ICS</text>
  </svg>
);

const AddToCalendar = ({ show }: AddToCalendarProps) => {
  const icsData = encodeURIComponent(calendarFile(show));
  const isTimedSingleDayShow = !!show.show_time && !show.show_start_date;
  const durationNote = isTimedSingleDayShow
    ? ` (estimated ${DEFAULT_EVENT_DURATION_HOURS}-hour duration)`
    : '';

  return (
    <div className="calendar-export" role="group" aria-label="Add to calendar">
      <span className="calendar-export__label">Add to calendar</span>
      <div className="calendar-export__actions">
        <a
          className="calendar-export__icon"
          href={googleCalendarUrl(show)}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`Add to Google Calendar${durationNote}`}
          title={`Google Calendar${durationNote}`}
        >
          <GoogleCalendarIcon />
        </a>
        <a
          className="calendar-export__icon"
          href={`data:text/calendar;charset=utf-8,${icsData}`}
          download={calendarFilename(show)}
          aria-label={`Download .ics calendar file${durationNote}`}
          title={`Download .ics${durationNote}`}
        >
          <IcsIcon />
        </a>
      </div>
    </div>
  );
};

export default AddToCalendar;