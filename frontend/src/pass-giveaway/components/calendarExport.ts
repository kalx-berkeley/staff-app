import { addCalendarDays, pacificWallTimeToInstant } from '../../common/dateTime';

export interface CalendarExportShow {
  id: number;
  event_name: string;
  show_date: string;
  show_start_date: string | null;
  show_time: string | null;
  venue: {
    name: string;
    address: string | null;
  };
}

export const DEFAULT_EVENT_DURATION_HOURS = 3;

function compactUtc(date: Date): string {
  return date.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
}

function compactDate(date: string): string {
  return date.replace(/-/g, '');
}

function escapeIcsText(value: string): string {
  return value
    .replace(/\\/g, '\\\\')
    .replace(/\r?\n/g, '\\n')
    .replace(/,/g, '\\,')
    .replace(/;/g, '\\;');
}

function eventLocation(show: CalendarExportShow): string {
  return [show.venue.name, show.venue.address].filter(Boolean).join(', ');
}

function eventTimes(show: CalendarExportShow): {
  allDay: boolean;
  start: string;
  end: string;
} {
  const startDate = show.show_start_date ?? show.show_date;
  const allDay = !!show.show_start_date || !show.show_time;

  if (allDay) {
    return {
      allDay: true,
      start: compactDate(startDate),
      // iCalendar and Google Calendar use an exclusive end date for all-day events.
      end: compactDate(addCalendarDays(show.show_date, 1)),
    };
  }

  const start = pacificWallTimeToInstant(startDate, show.show_time!);
  const end = new Date(start.getTime() + DEFAULT_EVENT_DURATION_HOURS * 60 * 60 * 1000);
  return { allDay: false, start: compactUtc(start), end: compactUtc(end) };
}

function eventDescription(allDay: boolean): string {
  return allDay
    ? 'KALX staff pass for this event.'
    : `KALX staff pass for this event. Event length is estimated at ${DEFAULT_EVENT_DURATION_HOURS} hours because an end time is not listed.`;
}

export function googleCalendarUrl(show: CalendarExportShow): string {
  const times = eventTimes(show);
  const params = new URLSearchParams({
    action: 'TEMPLATE',
    text: show.event_name,
    dates: `${times.start}/${times.end}`,
    details: eventDescription(times.allDay),
    location: eventLocation(show),
  });
  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

export function calendarFile(show: CalendarExportShow, now = new Date()): string {
  const times = eventTimes(show);
  const startLine = times.allDay
    ? `DTSTART;VALUE=DATE:${times.start}`
    : `DTSTART:${times.start}`;
  const endLine = times.allDay
    ? `DTEND;VALUE=DATE:${times.end}`
    : `DTEND:${times.end}`;
  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//KALX//Staff App//EN',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
    'BEGIN:VEVENT',
    `UID:staff-pass-show-${show.id}@kalx.berkeley.edu`,
    `DTSTAMP:${compactUtc(now)}`,
    startLine,
    endLine,
    `SUMMARY:${escapeIcsText(show.event_name)}`,
    `LOCATION:${escapeIcsText(eventLocation(show))}`,
    `DESCRIPTION:${escapeIcsText(eventDescription(times.allDay))}`,
    'END:VEVENT',
    'END:VCALENDAR',
    '',
  ];
  return lines.join('\r\n');
}

export function calendarFilename(show: CalendarExportShow): string {
  const safeName = show.event_name
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/gi, '-')
    .replace(/^-|-$/g, '')
    .toLowerCase();
  return `${safeName || 'kalx-show'}-${show.show_date}.ics`;
}