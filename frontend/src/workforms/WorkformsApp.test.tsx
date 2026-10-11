import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import App from '../App';
import { AuthProvider } from '../common/contexts/AuthContext';
import { usersAPI } from '../common/api';
import type { UserResponse } from '../common/types';
import { reviewAPI, workformsAPI } from './api';
import type { ReviewItem, ReviewQueue, Workform } from './types';

vi.mock('../common/api', () => ({
  AUTH_DIAG_KEY: 'kalx_auth_diag',
  usersAPI: { getMe: vi.fn() },
  handleAPIError: vi.fn(),
}));

vi.mock('./api', () => ({
  workformsAPI: {
    departments: vi.fn(),
    mine: vi.fn(),
    get: vi.fn(),
    addEntry: vi.fn(),
    updateEntry: vi.fn(),
    deleteEntry: vi.fn(),
    submit: vi.fn(),
    preferences: vi.fn(),
    updatePreferences: vi.fn(),
  },
  reviewAPI: {
    overview: vi.fn(),
    pending: vi.fn(),
    queue: vi.fn(),
    decide: vi.fn(),
  },
}));

const user = (overrides: Partial<UserResponse> = {}): UserResponse => ({
  email: 'amy@example.com',
  role: 'staff',
  is_dj_network: false,
  is_station_office_network: false,
  is_department_head: false,
  profile: { id: 1, name: 'Amy Adams', phone: '510-555-0001', dj_name: null, is_sublist_dj: false },
  ...overrides,
});

const workform = (overrides: Partial<Workform> = {}): Workform => ({
  month: '2026-10',
  is_open: true,
  is_current_month: true,
  deadline: '2026-11-06T07:59:59Z',
  status: 'draft',
  has_unsent_changes: false,
  submitted_at: null,
  is_late: false,
  would_be_late: false,
  entries: [
    {
      id: 1,
      department: 'Promotions',
      hours: 2,
      description: 'Ran the table',
      work_date: '2026-10-03',
      loa_flag: null,
    },
    {
      id: 2,
      department: 'Promotions',
      hours: 1.5,
      description: 'Postered',
      work_date: null,
      loa_flag: null,
    },
  ],
  results: {},
  loa_start: null,
  loa_end: null,
  loa_overlaps_month: false,
  ...overrides,
});

const renderAt = async (path: string, me: UserResponse = user()) => {
  window.history.pushState({}, '', path);
  vi.mocked(usersAPI.getMe).mockResolvedValue(me);
  render(
    <AuthProvider>
      <App />
    </AuthProvider>
  );
};

describe('KALX Workforms month page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(workformsAPI.mine).mockResolvedValue({
      open_months: ['2026-10', '2026-09'],
      workforms: [
        {
          month: '2026-10',
          status: 'draft',
          is_open: true,
          is_late: false,
          total_hours: 3.5,
          results: {},
          loa_overlaps_month: false,
        },
        {
          month: '2026-09',
          status: 'not_started',
          is_open: true,
          is_late: false,
          total_hours: 0,
          results: {},
          loa_overlaps_month: false,
        },
      ],
    });
    vi.mocked(workformsAPI.departments).mockResolvedValue({
      own: ['Promotions'],
      other: ['Music', 'Special Events'],
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("shows this month's entries grouped by department with totals", async () => {
    vi.mocked(workformsAPI.get).mockResolvedValue(workform());
    await renderAt('/workforms/');

    expect(await screen.findByRole('heading', { name: 'October 2026' })).toBeInTheDocument();
    expect(screen.getByText('3.5 hours')).toBeInTheDocument();
    const card = screen.getByRole('heading', { name: 'Promotions' }).closest('section')!;
    expect(within(card).getByText('Oct 3')).toBeInTheDocument();
    expect(within(card).getByText('No date')).toBeInTheDocument();
    expect(screen.getByLabelText(/^Date/)).toHaveAttribute('min', '2026-10-01');
    expect(screen.getByLabelText(/^Date/)).toHaveAttribute('max', '2026-10-31');
    expect(screen.getByRole('link', { name: /September 2026/ })).toBeInTheDocument();
    expect(screen.getByRole('note')).toHaveTextContent(/not the official way to submit workforms/);
  });

  it('shows whether the month reaches the 6-hour minimum', async () => {
    vi.mocked(workformsAPI.get).mockResolvedValue(workform());
    await renderAt('/workforms/');
    expect(await screen.findByText('2.5 h short of the 6-hour minimum')).toBeInTheDocument();
    cleanup();

    vi.mocked(workformsAPI.get).mockResolvedValue(
      workform({
        entries: [
          {
            id: 1,
            department: 'Promotions',
            hours: 6,
            description: 'Ran the table',
            work_date: null,
            loa_flag: null,
          },
        ],
      })
    );
    await renderAt('/workforms/');
    expect(await screen.findByText(/6-hour minimum met/)).toBeInTheDocument();
    cleanup();

    vi.mocked(workformsAPI.get).mockResolvedValue(workform({ loa_overlaps_month: true }));
    await renderAt('/workforms/');
    expect(
      await screen.findByText('No 6-hour minimum during leave of absence')
    ).toBeInTheDocument();
  });

  it('checks hours before adding an entry', async () => {
    vi.mocked(workformsAPI.get).mockResolvedValue(workform({ entries: [], status: 'not_started' }));
    await renderAt('/workforms/');
    await screen.findByRole('heading', { name: 'Add work' });

    fireEvent.change(screen.getByLabelText('Hours'), { target: { value: '1.1' } });
    fireEvent.change(screen.getByLabelText('What did you do?'), { target: { value: 'Filing' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/quarter hours/);
    expect(workformsAPI.addEntry).not.toHaveBeenCalled();

    vi.mocked(workformsAPI.addEntry).mockResolvedValue(workform().entries[0]);
    fireEvent.change(screen.getByLabelText('Hours'), { target: { value: '1.25' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add' }));
    await waitFor(() =>
      expect(workformsAPI.addEntry).toHaveBeenCalledWith('2026-10', {
        department: 'Promotions',
        hours: 1.25,
        description: 'Filing',
        work_date: null,
      })
    );
  });

  it('confirms before submitting, warning when late', async () => {
    vi.mocked(workformsAPI.get).mockResolvedValue(workform({ would_be_late: true }));
    vi.mocked(workformsAPI.submit).mockResolvedValue(workform({ status: 'submitted' }));
    await renderAt('/workforms/');

    fireEvent.click(await screen.findByRole('button', { name: 'Submit workform' }));
    const dialog = screen.getByRole('dialog', { name: 'Confirm submission' });
    expect(dialog).toHaveTextContent('Submit 3.5 hours for October 2026 in Promotions?');
    expect(dialog).toHaveTextContent(/might not count/);
    fireEvent.click(within(dialog).getByRole('button', { name: 'Submit' }));
    await waitFor(() => expect(workformsAPI.submit).toHaveBeenCalledWith('2026-10'));
  });

  it('shows a locked workform read-only with decisions', async () => {
    vi.mocked(workformsAPI.get).mockResolvedValue(
      workform({
        status: 'locked',
        results: { Promotions: { hours: 3.5, description: '…', decision: 'Approved' } },
      })
    );
    await renderAt('/workforms/month/2026-10');

    expect(await screen.findByText(/has reviewed this workform/)).toBeInTheDocument();
    expect(screen.getByText('Approved')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Add work' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Submit/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument();
  });

  it('only offers the review tab to department heads', async () => {
    vi.mocked(workformsAPI.get).mockResolvedValue(workform());
    await renderAt('/workforms/');
    await screen.findByRole('heading', { name: 'October 2026' });
    expect(screen.queryByRole('link', { name: 'Review' })).not.toBeInTheDocument();
  });
});

const item = (overrides: Partial<ReviewItem>): ReviewItem => ({
  airtable_record_id: 'rec1',
  staff_id: 1,
  staff_name: 'Sam',
  hours: 2,
  description: '(2h): work',
  decision: null,
  entries: [{ hours: 2, description: 'work', work_date: null, loa_flag: null }],
  edited_in_airtable: false,
  submitted_at: '2026-10-02T17:00:00',
  is_late: false,
  loa_start: null,
  loa_end: null,
  loa_overlaps_month: false,
  ...overrides,
});

describe('KALX Workforms review page', () => {
  const queue = (items: ReviewItem[]): ReviewQueue => {
    const reviewed = items.filter((i) => i.decision).length;
    return {
      month: '2026-09',
      department: 'Music',
      items,
      total: items.length,
      reviewed,
      remaining: items.length - reviewed,
    };
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(reviewAPI.overview).mockResolvedValue({
      is_operations_head: false,
      own_departments: ['Music'],
      fallback_departments: [],
      default_month: '2026-09',
      default_department: 'Music',
      months: ['2026-10', '2026-09'],
    });
    vi.mocked(reviewAPI.pending).mockResolvedValue({ month: '2026-09', pending: { Music: 2 } });
  });

  afterEach(() => {
    cleanup();
  });

  it('shows progress and moves to the next person after a decision', async () => {
    const items = [
      item({ airtable_record_id: 'rec1', staff_name: 'Ada', is_late: true }),
      item({ airtable_record_id: 'rec2', staff_name: 'Bo', decision: 'Approved' }),
      item({
        airtable_record_id: 'rec3',
        staff_name: 'Cy',
        loa_overlaps_month: true,
        loa_start: '2026-09-10',
        entries: [{ hours: 2, description: 'work', work_date: '2026-09-12', loa_flag: 'inside' }],
      }),
    ];
    vi.mocked(reviewAPI.queue).mockResolvedValue(queue(items));
    vi.mocked(reviewAPI.decide).mockResolvedValue({ ...items[0], decision: 'Denied' });
    await renderAt('/workforms/review', user({ is_department_head: true }));

    expect(await screen.findByText('1 of 3 reviewed, 2 remaining')).toBeInTheDocument();
    expect(reviewAPI.queue).toHaveBeenCalledWith('2026-09', 'Music');
    expect(screen.getByRole('heading', { name: 'Ada' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Deny' }));
    await waitFor(() => expect(reviewAPI.decide).toHaveBeenCalledWith('rec1', 'Music', 'Denied'));
    expect(await screen.findByText('2 of 3 reviewed, 1 remaining')).toBeInTheDocument();
    // Skips Bo, who's already approved
    expect(screen.getByRole('heading', { name: 'Cy' })).toBeInTheDocument();
    expect(screen.getByText('During leave of absence')).toBeInTheDocument();
  });

  it('notes hours edited in Airtable', async () => {
    vi.mocked(reviewAPI.queue).mockResolvedValue(
      queue([item({ hours: 5, edited_in_airtable: true, description: '(5h): by hand' })])
    );
    await renderAt('/workforms/review/2026-09', user({ is_department_head: true }));
    expect(await screen.findByText(/changed in Airtable/)).toBeInTheDocument();
    expect(screen.getByText('(5h): by hand')).toBeInTheDocument();
  });

  it('sends people who aren’t heads back to their workform', async () => {
    vi.mocked(workformsAPI.mine).mockResolvedValue({ open_months: ['2026-10'], workforms: [] });
    vi.mocked(workformsAPI.departments).mockResolvedValue({ own: [], other: ['Music'] });
    vi.mocked(workformsAPI.get).mockResolvedValue(workform({ entries: [], status: 'not_started' }));
    await renderAt('/workforms/review');
    expect(await screen.findByRole('heading', { name: 'October 2026' })).toBeInTheDocument();
    expect(reviewAPI.overview).not.toHaveBeenCalled();
  });
});
