import { addCalendarDays, PACIFIC_TIME_ZONE } from '../../common/dateTime';

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

// RFC 5545 requires every TZID to be defined in the file. Google and Apple
// recognize the IANA name on its own, but Outlook relies on this block.
const PACIFIC_VTIMEZONE = [
  'BEGIN:VTIMEZONE',
  `TZID:${PACIFIC_TIME_ZONE}`,
  'BEGIN:DAYLIGHT',
  'TZOFFSETFROM:-0800',
  'TZOFFSETTO:-0700',
  'TZNAME:PDT',
  'DTSTART:19700308T020000',
  'RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU',
  'END:DAYLIGHT',
  'BEGIN:STANDARD',
  'TZOFFSETFROM:-0700',
  'TZOFFSETTO:-0800',
  'TZNAME:PST',
  'DTSTART:19701101T020000',
  'RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU',
  'END:STANDARD',
  'END:VTIMEZONE',
];

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

/**
 * Pacific wall-clock start and end as floating `YYYYMMDDTHHMMSS` strings. The
 * calendar app resolves them in Pacific time (PACIFIC_TIME_ZONE), including DST.
 */
function pacificWallTimes(date: string, time: string): { start: string; end: string } {
  const match = /^(\d{2}):(\d{2})(?::\d{2})?$/.exec(time);
  if (!match) throw new RangeError(`Invalid show time: ${time}`);
  const hour = Number(match[1]);
  const minute = match[2];
  const endHour = hour + DEFAULT_EVENT_DURATION_HOURS;
  const endDate = addCalendarDays(date, Math.floor(endHour / 24));
  const wallTime = (d: string, h: number) =>
    `${compactDate(d)}T${String(h % 24).padStart(2, '0')}${minute}00`;
  return { start: wallTime(date, hour), end: wallTime(endDate, endHour) };
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

  return { allDay: false, ...pacificWallTimes(startDate, show.show_time!) };
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
  if (!times.allDay) params.set('ctz', PACIFIC_TIME_ZONE);
  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

export function calendarFile(show: CalendarExportShow, now = new Date()): string {
  const times = eventTimes(show);
  const startLine = times.allDay
    ? `DTSTART;VALUE=DATE:${times.start}`
    : `DTSTART;TZID=${PACIFIC_TIME_ZONE}:${times.start}`;
  const endLine = times.allDay
    ? `DTEND;VALUE=DATE:${times.end}`
    : `DTEND;TZID=${PACIFIC_TIME_ZONE}:${times.end}`;
  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//KALX//Staff App//EN',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
    ...(times.allDay ? [] : PACIFIC_VTIMEZONE),
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