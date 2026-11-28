import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react';
import App from '../App';
import { renderWithAuth } from '../test/render';
import { usersAPI } from '../common/api';
import type { UserResponse } from '../common/types';
import { SUBSITES } from '../subsites';
import { analyticsAPI } from './api';
import type { Metric, TabResponse } from './types';

vi.mock('../common/api', () => ({
  AUTH_DIAG_KEY: 'kalx_auth_diag',
  // pass-giveaway/api.ts adds an interceptor to the client when it's imported
  default: {
    post: vi.fn(() => Promise.resolve({})),
    interceptors: { request: { use: vi.fn() } },
  },
  usersAPI: { getMe: vi.fn() },
  impersonationAPI: { end: vi.fn() },
  handleAPIError: vi.fn(),
}));

vi.mock('./api', () => ({ analyticsAPI: { getTab: vi.fn() } }));

const user = (overrides: Partial<UserResponse> = {}): UserResponse => ({
  email: 'promo@example.com',
  role: 'promotions',
  is_dj_network: false,
  is_station_office_network: false,
  is_site_admin: false,
  is_promotions_admin: true,
  ...overrides,
});

const explanation = {
  formula: 'Pass pairs given away ÷ pass pairs.',
  date_basis: 'Show date',
  includes: 'Published and closed shows.',
  excludes: null,
  data_since: null,
};

const METRICS: Metric[] = [
  {
    id: 'on_air_utilization',
    title: 'On-air utilization',
    kind: 'stat',
    value: 0.5,
    format: 'percent',
    note: '2 of 4 pass pairs',
    explanation,
  },
  {
    id: 'venues',
    title: 'Venues',
    kind: 'table',
    top: 2,
    explanation,
    columns: [
      { key: 'venue', label: 'Venue', format: 'text', link: '/venues/{venue_id}' },
      { key: 'shows', label: 'Shows', format: 'number', link: null, help: 'Shows in the window.' },
      { key: 'balance', label: 'Balance', format: 'points', link: null },
    ],
    rows: [
      { venue: 'The Fox', venue_id: 1, shows: 5, balance: 20 },
      { venue: 'Ivy Room', venue_id: 2, shows: 1, balance: -10, _low_sample: true },
      {
        venue: 'Cornerstone',
        venue_id: 3,
        shows: 9,
        balance: 0,
        _flag: true,
        _details: {
          columns: [{ key: 'show', label: 'Show', format: 'text', link: null }],
          rows: [{ show: 'Big Night' }],
        },
      },
    ],
  },
];

const response = (overrides: Partial<TabResponse> = {}): TabResponse => ({
  window: { start: '2026-11-01', end: '2026-11-30', preset: 'this_month', label: 'This month' },
  title: null,
  metrics: METRICS,
  ...overrides,
});

const renderAnalytics = async (path = '/analytics/', me: UserResponse = user()) => {
  window.history.pushState({}, '', path);
  vi.mocked(usersAPI.getMe).mockResolvedValue(me);
  await renderWithAuth(<App />);
};

describe('KALX Staff Analytics', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(analyticsAPI.getTab).mockResolvedValue(response());
    localStorage.clear();
  });

  afterEach(() => {
    cleanup();
    window.history.pushState({}, '', '/');
  });

  it('is offered only to site admins and promotions admins', () => {
    const analytics = SUBSITES.find((s) => s.basePath === '/analytics')!;
    expect(analytics.isAvailable(user())).toBe(true);
    expect(analytics.isAvailable(user({ is_promotions_admin: false, is_site_admin: true }))).toBe(true);
    expect(analytics.isAvailable(user({ is_promotions_admin: false }))).toBe(false);
    expect(analytics.isAvailable(null)).toBe(false);
  });

  it('shows the overview with the default window', async () => {
    await renderAnalytics();
    expect(await screen.findByText('50%')).toBeInTheDocument();
    expect(screen.getByText('2 of 4 pass pairs')).toBeInTheDocument();
    expect(analyticsAPI.getTab).toHaveBeenCalledWith('overview', { preset: 'this_month' }, {});
  });

  it('explains how a metric is calculated', async () => {
    await renderAnalytics();
    await screen.findByText('50%');
    fireEvent.click(screen.getByRole('button', { name: 'How "On-air utilization" is calculated' }));
    const popover = screen.getByRole('dialog', { name: 'How "On-air utilization" is calculated' });
    expect(within(popover).getByText('Pass pairs given away ÷ pass pairs.')).toBeInTheDocument();
    expect(within(popover).getByText('Show date')).toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('explains what a column means', async () => {
    await renderAnalytics();
    const table = await screen.findByRole('table', { name: 'Venues' });
    fireEvent.click(within(table).getByRole('button', { name: 'What "Shows" means' }));
    const popover = screen.getByRole('dialog', { name: 'What "Shows" means' });
    expect(within(popover).getByText('Shows in the window.')).toBeInTheDocument();
    // Name columns have none
    expect(within(table).queryByRole('button', { name: 'What "Venue" means' })).not.toBeInTheDocument();
  });

  it('gives every section an anchor and copies a link to it', async () => {
    const writeText = vi.fn(() => Promise.resolve());
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } });
    await renderAnalytics();
    await screen.findByText('50%');
    expect(document.getElementById('on-air-utilization')).not.toBeNull();
    const link = screen.getByRole('link', { name: 'Link to "Venues" (copies the link)' });
    expect(link).toHaveAttribute('href', '#venues');
    expect(link.closest('section')).toHaveAttribute('id', 'venues');
    fireEvent.click(link);
    // The window is spelled out, so the link keeps showing this window
    expect(writeText).toHaveBeenCalledWith(
      `${window.location.origin}/analytics/?preset=this_month#venues`,
    );
    expect(await screen.findByText('Link copied')).toBeInTheDocument();
  });

  it('passes the win to the winner page', async () => {
    vi.mocked(analyticsAPI.getTab).mockResolvedValue(response({ title: 'Jane Doe' }));
    await renderAnalytics('/analytics/winners/12?preset=all_time');
    expect(await screen.findByRole('heading', { name: 'Jane Doe' })).toBeInTheDocument();
    expect(analyticsAPI.getTab).toHaveBeenCalledWith('winner', { preset: 'all_time' }, { win_id: '12' });
    expect(screen.getByRole('link', { name: '← All on-air winners' })).toHaveAttribute(
      'href',
      '/analytics/winners?preset=all_time',
    );
    expect(screen.getByRole('link', { name: 'On-air winners' })).toHaveAttribute(
      'href',
      '/analytics/winners?preset=all_time',
    );
  });

  it('changes the window and keeps it in the URL', async () => {
    await renderAnalytics();
    await screen.findByText('50%');
    fireEvent.change(screen.getByRole('combobox', { name: 'Time window' }), {
      target: { value: 'last_quarter' },
    });
    await waitFor(() =>
      expect(analyticsAPI.getTab).toHaveBeenLastCalledWith('overview', { preset: 'last_quarter' }, {}),
    );
    expect(window.location.search).toBe('?preset=last_quarter');
    // Tab links keep the window
    expect(screen.getByRole('link', { name: 'Venues' })).toHaveAttribute(
      'href',
      '/analytics/venues?preset=last_quarter',
    );
    await screen.findByText('50%');
  });

  it('applies a custom range', async () => {
    await renderAnalytics();
    await screen.findByText('50%');
    fireEvent.change(screen.getByRole('combobox', { name: 'Time window' }), {
      target: { value: 'custom' },
    });
    fireEvent.change(screen.getByLabelText('From'), { target: { value: '2026-01-01' } });
    fireEvent.change(screen.getByLabelText('To'), { target: { value: '2026-03-31' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));
    await waitFor(() =>
      expect(analyticsAPI.getTab).toHaveBeenLastCalledWith(
        'overview',
        { from: '2026-01-01', to: '2026-03-31' },
        {},
      ),
    );
    await screen.findByText('50%');
  });

  it('shows the top rows, then all of them, with details and flags', async () => {
    await renderAnalytics('/analytics/?preset=all_time');
    const table = await screen.findByRole('table', { name: 'Venues' });
    expect(within(table).getByText('The Fox')).toBeInTheDocument();
    expect(within(table).queryByText('Cornerstone')).not.toBeInTheDocument();
    expect(within(table).getByText('low sample')).toBeInTheDocument();
    expect(within(table).getByRole('link', { name: 'The Fox' })).toHaveAttribute(
      'href',
      '/analytics/venues/1?preset=all_time',
    );

    fireEvent.click(screen.getByRole('button', { name: 'Show all 3' }));
    const row = within(table).getByText('Cornerstone').closest('tr')!;
    expect(row).toHaveClass('analytics-row-flag');
    fireEvent.click(within(row).getByRole('button', { name: 'Show details' }));
    expect(screen.getByText('Big Night')).toBeInTheDocument();
  });

  it('sorts a table by a column', async () => {
    await renderAnalytics();
    const table = await screen.findByRole('table', { name: 'Venues' });
    fireEvent.click(screen.getByRole('button', { name: 'Show all 3' }));
    fireEvent.click(within(table).getByRole('button', { name: 'Shows' }));
    const venues = within(table)
      .getAllByRole('row')
      .slice(1)
      // The first cell is the details toggle
      .map((r) => r.querySelectorAll('td')[1]?.textContent);
    expect(venues[0]).toContain('Cornerstone');
    expect(venues[2]).toContain('Ivy Room');
  });

  it('passes the venue to the venue page and shows its title', async () => {
    vi.mocked(analyticsAPI.getTab).mockResolvedValue(response({ title: 'The Fox' }));
    await renderAnalytics('/analytics/venues/7?preset=this_year');
    expect(await screen.findByRole('heading', { name: 'The Fox' })).toBeInTheDocument();
    expect(analyticsAPI.getTab).toHaveBeenCalledWith('venue', { preset: 'this_year' }, { venue_id: '7' });
    expect(screen.getByRole('link', { name: '← All venues' })).toHaveAttribute(
      'href',
      '/analytics/venues?preset=this_year',
    );
  });

  it('shows a chart, and its numbers as a table', async () => {
    vi.mocked(analyticsAPI.getTab).mockResolvedValue(
      response({
        metrics: [
          {
            id: 'users_per_day',
            title: 'Signed-in users per day',
            kind: 'series',
            chart: 'line',
            explanation,
            x: { key: 'day', label: 'Day', format: 'date', link: null },
            series: [{ key: 'users', label: 'Users', format: 'number', link: null }],
            rows: [{ day: '2026-11-08', users: 4 }],
          },
        ],
      }),
    );
    await renderAnalytics('/analytics/usage');
    fireEvent.click(await screen.findByRole('button', { name: 'Show table' }));
    const table = screen.getByRole('table', { name: 'Signed-in users per day' });
    expect(within(table).getByText('4')).toBeInTheDocument();
  });

  it('sends anyone else to the home page', async () => {
    const replace = vi.fn();
    const original = window.location;
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { ...original, pathname: '/analytics/', replace },
    });
    try {
      vi.mocked(usersAPI.getMe).mockResolvedValue(user({ is_promotions_admin: false, role: 'staff' }));
      await renderWithAuth(<App />);
      expect(replace).toHaveBeenCalledWith('/');
      expect(analyticsAPI.getTab).not.toHaveBeenCalled();
    } finally {
      Object.defineProperty(window, 'location', { configurable: true, value: original });
    }
  });
});
