import { describe, expect, it } from 'vitest';
import type { CalendarExportShow } from './calendarExport';
import { calendarFile, calendarFilename, googleCalendarUrl } from './calendarExport';

const show: CalendarExportShow = {
  id: 42,
  event_name: 'Band, One; Two',
  show_date: '2026-07-05',
  show_start_date: null,
  show_time: '19:00',
  venue: { name: 'The Venue', address: '123 Main St, Berkeley' },
};

describe('calendar export', () => {
  it('exports timed events in Pacific time with a three-hour default duration', () => {
    const file = calendarFile(show, new Date('2026-01-02T03:04:05Z'));

    expect(file).toContain('DTSTART;TZID=America/Los_Angeles:20260705T190000');
    expect(file).toContain('DTEND;TZID=America/Los_Angeles:20260705T220000');
    expect(file).toContain('BEGIN:VTIMEZONE\r\nTZID:America/Los_Angeles');
    expect(file).toContain('SUMMARY:Band\\, One\\; Two');
    expect(file).toContain('LOCATION:The Venue\\, 123 Main St\\, Berkeley');
    expect(file).toContain('DTSTAMP:20260102T030405Z');
  });

  it('exports multi-day shows as all-day events through the inclusive end date', () => {
    const multiDayShow = {
      ...show,
      show_start_date: '2026-12-05',
      show_date: '2026-12-06',
    };
    const file = calendarFile(multiDayShow);
    const googleUrl = new URL(googleCalendarUrl(multiDayShow));

    expect(file).toContain('DTSTART;VALUE=DATE:20261205');
    expect(file).toContain('DTEND;VALUE=DATE:20261207');
    expect(file).not.toContain('VTIMEZONE');
    expect(googleUrl.searchParams.get('dates')).toBe('20261205/20261207');
    expect(googleUrl.searchParams.has('ctz')).toBe(false);
  });

  it('exports a show with no listed time as an all-day event', () => {
    const noTimeShow = { ...show, show_time: null };
    expect(calendarFile(noTimeShow)).toContain('DTSTART;VALUE=DATE:20260705');
    expect(calendarFile(noTimeShow)).toContain('DTEND;VALUE=DATE:20260706');
  });

  it('rolls the end time past midnight onto the next day', () => {
    const lateShow = { ...show, show_date: '2026-12-31', show_time: '22:30' };
    const file = calendarFile(lateShow);
    expect(file).toContain('DTSTART;TZID=America/Los_Angeles:20261231T223000');
    expect(file).toContain('DTEND;TZID=America/Los_Angeles:20270101T013000');
  });

  it('creates a safe descriptive download filename', () => {
    expect(calendarFilename(show)).toBe('band-one-two-2026-07-05.ics');
  });

  it('includes the venue and event name in the Google Calendar link', () => {
    const url = new URL(googleCalendarUrl(show));

    expect(url.searchParams.get('text')).toBe('Band, One; Two');
    expect(url.searchParams.get('location')).toBe('The Venue, 123 Main St, Berkeley');
    expect(url.searchParams.get('dates')).toBe('20260705T190000/20260705T220000');
    expect(url.searchParams.get('ctz')).toBe('America/Los_Angeles');
  });
});