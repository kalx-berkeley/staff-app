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

    expect(file).toContain('DTSTART:20260706T020000Z');
    expect(file).toContain('DTEND:20260706T050000Z');
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
    expect(googleUrl.searchParams.get('dates')).toBe('20261205/20261207');
  });

  it('exports a show with no listed time as an all-day event', () => {
    const noTimeShow = { ...show, show_time: null };
    expect(calendarFile(noTimeShow)).toContain('DTSTART;VALUE=DATE:20260705');
    expect(calendarFile(noTimeShow)).toContain('DTEND;VALUE=DATE:20260706');
  });

  it('uses the Pacific standard-time offset for winter events', () => {
    const winterShow = { ...show, show_date: '2026-12-05' };
    expect(calendarFile(winterShow)).toContain('DTSTART:20261206T030000Z');
  });

  it('creates a safe descriptive download filename', () => {
    expect(calendarFilename(show)).toBe('band-one-two-2026-07-05.ics');
  });

  it('includes the venue and event name in the Google Calendar link', () => {
    const url = new URL(googleCalendarUrl(show));

    expect(url.searchParams.get('text')).toBe('Band, One; Two');
    expect(url.searchParams.get('location')).toBe('The Venue, 123 Main St, Berkeley');
    expect(url.searchParams.get('dates')).toBe('20260706T020000Z/20260706T050000Z');
  });
});