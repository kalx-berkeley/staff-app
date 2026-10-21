import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react';
import App from '../App';
import { renderWithAuth } from '../test/render';
import { usersAPI } from '../common/api';
import type { UserResponse } from '../common/types';
import { reviewAPI, workformsAPI } from './api';
import type { DepartmentPeople, ReviewItem, ReviewQueue, Workform } from './types';

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
    staffWorkforms: vi.fn(),
    staffWorkform: vi.fn(),
  },
  reviewAPI: {
    overview: vi.fn(),
    pending: vi.fn(),
    queue: vi.fn(),
    decide: vi.fn(),
    people: vi.fn(),
    workTypes: vi.fn(),
    updateWorkTypes: vi.fn(),
  },
}));

const user = (overrides: Partial<UserResponse> = {}): UserResponse => ({
  email: 'amy@example.com',
  role: 'staff',
  is_dj_network: false,
  is_station_office_network: false,
  is_department_head: false,
  workforms_enabled: true,
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
  await renderWithAuth(<App />);
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
      work_types: {},
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

  it("offers the department's work types, with free text when allowed", async () => {
    vi.mocked(workformsAPI.departments).mockResolvedValue({
      own: ['Promotions'],
      other: ['Music'],
      work_types: {
        Promotions: { work_types: ['Tabling', 'Postering'], allow_free_text: true },
        Music: { work_types: ['Filing CDs'], allow_free_text: false },
      },
    });
    vi.mocked(workformsAPI.get).mockResolvedValue(workform({ entries: [], status: 'not_started' }));
    vi.mocked(workformsAPI.addEntry).mockResolvedValue(workform().entries[0]);
    await renderAt('/workforms/');
    await screen.findByRole('heading', { name: 'Add work' });

    fireEvent.change(screen.getByLabelText('Hours'), { target: { value: '1' } });
    expect(screen.queryByLabelText('Describe the work')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Add' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Choose the type of work');

    fireEvent.change(screen.getByLabelText('What did you do?'), { target: { value: 'Tabling' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add' }));
    await waitFor(() =>
      expect(workformsAPI.addEntry).toHaveBeenLastCalledWith('2026-10', {
        department: 'Promotions',
        hours: 1,
        description: 'Tabling',
        work_date: null,
      })
    );

    fireEvent.change(screen.getByLabelText('Hours'), { target: { value: '2' } });
    fireEvent.change(screen.getByLabelText('What did you do?'), { target: { value: ' other' } });
    fireEvent.change(screen.getByLabelText('Describe the work'), {
      target: { value: 'Made a flyer' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Add' }));
    await waitFor(() =>
      expect(workformsAPI.addEntry).toHaveBeenLastCalledWith('2026-10', {
        department: 'Promotions',
        hours: 2,
        description: 'Made a flyer',
        work_date: null,
      })
    );

    // Music only allows its work types
    fireEvent.change(screen.getByLabelText('Department'), { target: { value: 'Music' } });
    const options = within(screen.getByLabelText('What did you do?'))
      .getAllByRole('option')
      .map((o) => o.textContent);
    expect(options).toEqual(['Choose the type of work…', 'Filing CDs']);
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

  it('only offers the review and people tabs to department heads', async () => {
    vi.mocked(workformsAPI.get).mockResolvedValue(workform());
    await renderAt('/workforms/');
    await screen.findByRole('heading', { name: 'October 2026' });
    expect(screen.getByRole('link', { name: 'My workform' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Review' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'People' })).not.toBeInTheDocument();
  });

  it("tells department heads they don't need to submit a workform", async () => {
    vi.mocked(workformsAPI.get).mockResolvedValue(workform());
    await renderAt('/workforms/', user({ is_department_head: true }));
    expect(await screen.findByText(/don't need to submit a workform/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Staff view' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'People' })).toBeInTheDocument();
    expect(screen.queryByText(/6-hour minimum/)).not.toBeInTheDocument();
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
    vi.mocked(workformsAPI.departments).mockResolvedValue({ own: [], other: ['Music'], work_types: {} });
    vi.mocked(workformsAPI.get).mockResolvedValue(workform({ entries: [], status: 'not_started' }));
    await renderAt('/workforms/review');
    expect(await screen.findByRole('heading', { name: 'October 2026' })).toBeInTheDocument();
    expect(reviewAPI.overview).not.toHaveBeenCalled();
  });
});

describe('KALX Workforms people page', () => {
  const people = (overrides: Partial<DepartmentPeople> = {}): DepartmentPeople => ({
    department: 'Music',
    months: ['2026-07', '2026-08', '2026-09'],
    min_months: 2,
    people: [
      {
        staff_id: 1,
        staff_name: 'Sam',
        is_current_staff: true,
        months_reported: 2,
        total_hours: 5,
        hours: { '2026-08': 3, '2026-09': 2 },
      },
      {
        staff_id: 2,
        staff_name: 'Lee',
        is_current_staff: false,
        months_reported: 3,
        total_hours: 9,
        hours: { '2026-07': 4, '2026-08': 4, '2026-09': 1 },
      },
    ],
    ...overrides,
  });

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(reviewAPI.overview).mockResolvedValue({
      is_operations_head: false,
      own_departments: ['Music', 'Promotions'],
      fallback_departments: [],
      default_month: '2026-09',
      default_department: 'Promotions',
      months: ['2026-10', '2026-09'],
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('lists who reported hours in 2 of the last 3 months by default', async () => {
    vi.mocked(reviewAPI.people).mockResolvedValue(people());
    await renderAt('/workforms/people', user({ is_department_head: true }));

    const sam = (await screen.findByRole('rowheader', { name: 'Sam' })).closest('tr')!;
    expect(reviewAPI.people).toHaveBeenCalledWith('Music', 3, 2);
    expect(
      within(sam)
        .getAllByRole('cell')
        .map((c) => c.textContent)
    ).toEqual(['—', '3 h', '2 h', '5 h']);
    expect(screen.getByText('Not current staff')).toBeInTheDocument();
    expect(screen.getByText(/from July 2026 to September 2026/)).toBeInTheDocument();
  });

  it('keeps the months with hours within the months considered', async () => {
    vi.mocked(reviewAPI.people).mockResolvedValue(people());
    await renderAt('/workforms/people', user({ is_department_head: true }));
    await screen.findByRole('rowheader', { name: 'Sam' });

    vi.mocked(reviewAPI.people).mockResolvedValue(
      people({ months: ['2026-09'], min_months: 1, people: [] })
    );
    fireEvent.change(screen.getByLabelText('Out of the last'), { target: { value: '1' } });
    expect(await screen.findByText('No one matches.')).toBeInTheDocument();
    expect(reviewAPI.people).toHaveBeenLastCalledWith('Music', 1, 1);
  });
});

describe("KALX Workforms: a site admin viewing someone else's workforms", () => {
  const admin = user({ email: 'boss@example.com', is_site_admin: true });

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(workformsAPI.staffWorkforms).mockResolvedValue({
      open_months: ['2026-10'],
      staff_name: 'Zed Zulu',
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
      ],
    });
    vi.mocked(workformsAPI.staffWorkform).mockResolvedValue(
      workform({ staff_name: 'Zed Zulu' }),
    );
  });

  afterEach(() => {
    cleanup();
  });

  it('shows their month read-only', async () => {
    await renderAt('/workforms/staff/5/month/2026-10', admin);

    expect(await screen.findByText(/Viewing Zed Zulu’s workform/)).toBeInTheDocument();
    expect(workformsAPI.staffWorkform).toHaveBeenCalledWith(5, '2026-10');
    expect(workformsAPI.departments).not.toHaveBeenCalled();
    expect(screen.getByText('Ran the table')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Submit workform/ })).not.toBeInTheDocument();
    expect(screen.queryByText('Add work')).not.toBeInTheDocument();
  });

  it('shows their past workforms', async () => {
    await renderAt('/workforms/staff/5', admin);

    expect(await screen.findByText(/Viewing Zed Zulu’s workforms/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'October 2026' })).toHaveAttribute(
      'href',
      '/workforms/staff/5/month/2026-10',
    );
    expect(screen.queryByRole('link', { name: 'Finish and submit it' })).not.toBeInTheDocument();
  });

  it('is only for site admins', async () => {
    vi.mocked(workformsAPI.mine).mockResolvedValue({ open_months: ['2026-10'], workforms: [] });
    vi.mocked(workformsAPI.get).mockResolvedValue(workform());
    vi.mocked(workformsAPI.departments).mockResolvedValue({
      own: ['Promotions'],
      other: [],
      work_types: {},
    });
    await renderAt('/workforms/staff/5', user());

    await waitFor(() => expect(window.location.pathname).toBe('/workforms'));
    expect(workformsAPI.staffWorkforms).not.toHaveBeenCalled();
    await screen.findByText('Add work');
  });
});

describe('KALX Workforms work types page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(reviewAPI.overview).mockResolvedValue({
      is_operations_head: false,
      own_departments: ['Music', 'Promotions'],
      fallback_departments: [],
      default_month: '2026-09',
      default_department: 'Music',
      months: ['2026-10', '2026-09'],
    });
    vi.mocked(reviewAPI.workTypes).mockResolvedValue({
      work_types: ['Filing CDs', 'Reviews'],
      allow_free_text: true,
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('is only for department heads', async () => {
    vi.mocked(workformsAPI.mine).mockResolvedValue({ open_months: ['2026-10'], workforms: [] });
    vi.mocked(workformsAPI.departments).mockResolvedValue({
      own: [],
      other: ['Music'],
      work_types: {},
    });
    vi.mocked(workformsAPI.get).mockResolvedValue(workform({ entries: [], status: 'not_started' }));
    await renderAt('/workforms/work-types');
    expect(await screen.findByRole('heading', { name: 'October 2026' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Work types' })).not.toBeInTheDocument();
    expect(reviewAPI.workTypes).not.toHaveBeenCalled();
  });

  it('adds, reorders and removes work types, and saves them', async () => {
    vi.mocked(reviewAPI.updateWorkTypes).mockImplementation(async (_d, workTypes) => workTypes);
    await renderAt('/workforms/work-types', user({ is_department_head: true }));

    expect(await screen.findByText('Filing CDs')).toBeInTheDocument();
    expect(reviewAPI.workTypes).toHaveBeenCalledWith('Music');
    const freeText = screen.getByLabelText(/describe other work in their own words/);
    expect(freeText).toBeChecked();

    fireEvent.change(screen.getByLabelText('New work type'), { target: { value: ' Library ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add' }));
    fireEvent.click(screen.getByRole('button', { name: 'Move Library up' }));
    fireEvent.click(screen.getByRole('button', { name: 'Remove Filing CDs' }));
    fireEvent.click(freeText);
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Saved.');
    expect(reviewAPI.updateWorkTypes).toHaveBeenCalledWith('Music', {
      work_types: ['Library', 'Reviews'],
      allow_free_text: false,
    });
  });
});
