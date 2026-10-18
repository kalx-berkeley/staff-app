# Implementation Plan: KALX Workforms Sub-site

## Overview

A new sub-site at `/workforms/`, named "KALX Workforms", alongside
`/pass-giveaway/` and `/directory/`. Staff report their work each month on a
**workform**, which is like a timecard. It has two views:

- **Staff view** (every staff member whose Status includes Active). Staff add
  **entries** to this month's workform as they go. When they're done they submit
  it, and they can view past workforms and see each department's decision.
- **Review view** (department heads). Heads read the hours and descriptions
  staff submitted for their department, then approve or deny them, with a
  progress count.

Terms:

- **Entry**: one line a staff member records. It has hours, a description and
  an optional date in the workform's month.
- **Block**: all of one person's entries in one department for one month. On
  submit, each block becomes that department's three Airtable columns.
- **Workform**: one person's blocks for one month.

Drafts live only in the app's database. Submitting writes one record to the
Airtable workforms table. After that, Airtable is the source of truth for
submitted hours, descriptions and approvals, and the app keeps a local copy.

## Agreed decisions (from grilling session, 2026-10-11)

| # | Decision |
|---|----------|
| Q1 | Drafts, and their separate entries, are stored in the app's database. Airtable sees only submitted workforms. |
| Q2 | After submission, Airtable is the source of truth. A local copy is refreshed nightly, after each write, and when a head opens the review view. Hand edits in Airtable show up in the app. |
| Q3 | A submitted workform can be edited and resubmitted until any department has a decision (Approved or Denied). After that it is locked. |
| Q4 | Denied is final: those hours don't count. Heads tell the staff member outside the app. There is no denial reason. |
| Q5 | Drafts are only for the current month. Submitting is allowed any time during the month, up to the end of the 5th of the next month (deadline day set in config). After the deadline, last month can still be submitted, with a warning that late hours might not count. Older months and future months are not allowed. Months are calendar months in America/Los_Angeles. |
| Q6 | Any department can be chosen. The staff member's own departments (from `staff_department`) are listed first, and the rest are under "other". |
| Q7 | The department list comes from the "Department Heads" table, so adding a department only needs Airtable changes. |
| Q8 | The table name is a config setting: "Testing Workforms" on staging, "Workforms" (same structure) in production. Nothing from an earlier process is imported. |
| Q9 | Any head of a department can decide, and `audit_log` records which one. The **Operations** head reviews departments that have no head. |
| Q10 | Path `/workforms/`, name "KALX Workforms". |
| Q11 | Heads can use the staff view. Review of a head's own hours goes to the Operations head. |
| Q12 | The Operations head can review any department as a fallback, listed separately after their own departments. The Operations head may review their own Operations hours, and that is recorded in `audit_log`. |
| Q13 | There is no "whole month" vs "itemized" switch. Each department is one list of entries, and the date field is labeled "Date (recommended)". |
| Q14 | Hours come in steps of 0.25, must be more than 0, and have no maximum. A description is required, with no minimum length. The date is optional and limited to the workform's month, and it may be later than today. |
| Q15 | The combined description lists entries sorted by date, with undated entries last, one per line: `10-03 (2h): Ran the Halloween table at Sproul` / `(3h): Inventory of giveaway stock`. |
| Q16 | A 0-hour workform (no entries) can be submitted. It writes only Name and Month, and every department column stays blank. |
| Q17 | A head can change a decision or clear it back to pending at any time. Every change is recorded in `audit_log`. If every decision is cleared, the workform unlocks for staff edits again (Q3). |
| Q18 | The review view lists people on the left and one person's details on the right. It shows each entry with the total highlighted, and Approve/Deny moves to the next person automatically. Progress reads like "7 of 12 reviewed, 5 remaining". There's no approve-all. Late and LOA badges appear. If Airtable was edited by hand and no longer matches the entries, Airtable's values are shown with a note. The view opens on the most recent month with pending reviews and has a month selector. |
| Q19 | Emails go through `notification_service`, and each kind can be turned off in preferences. |
| Q20 | A Leave of Absence doesn't block anything. Someone who stops being Active loses access as they do elsewhere. Their submitted workforms stay reviewable, and their unsubmitted drafts are deleted. The review view flags hours submitted during an LOA. |
| Q21 | Impersonation (staging only) works fully: the impersonating user can do anything the impersonated user could, including approving and denying. |
| Q22 | Department heads are refreshed with the existing staff sync. If the Airtable write fails on submit, the workform stays a draft and the user sees an error. If a record for that person and month already exists, the app updates it instead of creating a duplicate. |
| Q23 | The existing `AIRTABLE_API_KEY` already has write access to the workforms table. |
| Q24 | LOA flags. A dated entry inside the LOA gets a clear warning. An undated entry in a month that overlaps the LOA gets a softer "may overlap LOA" note. Heads see both the person and the entries flagged. Staff see the warning but can still save. The warnings use the LOA dates saved at submission. |
| Q25 | Column names are not checked against the schema. A missing "<Dept> : …" column shows up as an Airtable error on submit, logged with the department and column name. |
| Q26 | Lateness is based on the record's Airtable **"Created Time"** field, so the first submission decides it and later edits don't change it. A record someone made by hand that the app then updates keeps the Created Time of when it was made, which is acceptable. The deadline is 23:59:59 Pacific on the 5th. |
| Q27 | Staff reminders go to Active staff who haven't submitted for the month (whether they have a draft or nothing), on the last day of the month and again on the 3rd. Anyone who has submitted, including a 0-hour workform, isn't reminded. Heads get one "N to review" email on the 6th. |
| Q28 | Department heads never get the "fill out your workform" reminder. |
| Q29 | `/workforms/settings` has its own preferences table, so the sub-site doesn't depend on pass giveaway code. Heads see the review-email switch, and other staff see the reminder switch. |

## Airtable

All tables are in the existing base (`AIRTABLE_BASE_ID`), accessed with
`AIRTABLE_API_KEY`.

**Workforms** (`AIRTABLE_WORKFORMS_TABLE_NAME`, default `"Testing Workforms"`;
production sets `"Workforms"`):

| Field | Type | App use |
|---|---|---|
| Workform ID | Autonumber | read only |
| Name | Link to "Online Staff App Directory" | written as `[staff.airtable_record_id]` |
| Month | Date | first day of the month, `YYYY-MM-01` |
| Created Time | Created time | read only; decides lateness |
| `<Dept> : Hours` | Number | total of the block's entries |
| `<Dept> : Description` | Long text | combined descriptions (Q15) |
| `<Dept> : Approved` | Multi-select, `Approved` / `Denied` | written by the review view; blank means pending |

The app never writes `<Dept> : Approved` on submit. It writes it only from the
review view. On a resubmit (Q3), the app sets Hours and Description for every
known department, and clears departments that no longer have entries.

**Department Heads**: "Department" links to "All departments" and resolves to
names through the existing `fetch_department_names`. "Department Heads" links
to "Online Staff App Directory" and is matched to `staff.airtable_record_id`.
No name matching is needed. The departments in this table are the workform
departments (Q7).

Linked fields come back as record IDs, so identity is matched entirely by
`staff.airtable_record_id`. A staff member with no record ID can't submit and
sees an error. This shouldn't happen after a sync.

## Backend

New sub-site package `backend/app/workforms/` with `routers/`, `services/` and
`schemas/`, following the sub-site rules in CLAUDE.md: it imports only from
`common` and the shared core, and nothing imports it except `main.py` and
`scheduler.py`.

### Config (`app/config.py`)

- `airtable_workforms_table_name: str = "Testing Workforms"`
- `airtable_department_heads_table_name: str = "Department Heads"`
- `workforms_deadline_day: int = 5`
- `workforms_operations_department: str = "Operations"`, the fallback reviewer department (Q9, Q11, Q12)

Add these to `.env.example`, and set the production table name in the deploy
config.

### Models (`app/models/`, one Alembic migration)

- `workforms`: one per staff member per month (`staff_id`, `month`, unique
  together). Holds the entries, plus the app's side of a submission:
  - `airtable_record_id`: null for a draft.
  - `first_submitted_at`, `last_submitted_at`.
  - `submitted_blocks` (JSON): what the last submission sent, per department,
    including its entries. Reviewers see these entries rather than later
    unsent edits. A difference from Airtable's values marks a hand edit there.
  - `loa_start_at_submit`, `loa_end_at_submit` (Q24).
- `workform_entries`: `workform_id` (cascade delete), `department`, `hours`
  (float, a multiple of 0.25), `description`, `work_date` (nullable). Sorted
  by date, then by when they were added.
- `workform_airtable_records`: the local copy of the Airtable workforms
  table. Every column comes from Airtable:
  - `airtable_record_id` (unique) and `staff_airtable_record_id` (the Name
    link)
  - `month`, and `created_time` (from Created Time)
  - `departments` (JSON: `{dept: {hours, description, approved}}`)
  - `refreshed_at`
- `workform_departments` and `department_heads`: copies of the "Department
  Heads" table, replaced in full on every sync. Departments are kept
  separately so a department with no head is still listed.
- `workform_preferences`: `staff_id` (unique), `reminder_emails_enabled`,
  `review_emails_enabled`. Both default to true.

### Services (`app/workforms/services/`)

- `airtable_client.py`: list (with pagination and an optional formula),
  get, create and patch records in the workforms table. Create and patch use
  `typecast: true`. Airtable errors are logged and raised as 502s that carry
  Airtable's message, so an unknown "<Dept> : Hours" column is named in the
  error (Q25).
- `records.py`:
  - Parses records into the local copy. "Denied" wins if a multi-select has
    both values.
  - `refresh_all` (the whole table, and drops records deleted in Airtable),
    `refresh_month` (`IS_SAME({Month}, …, 'month')`) and `refresh_one`.
  - `is_locked` and `record_for`.
- `months.py`: open months (this month and last), the deadline (23:59:59
  Pacific on `WORKFORMS_DEADLINE_DAY` of the next month), lateness, and
  parsing `YYYY-MM`.
- `departments.py`:
  - `sync_department_heads`. If Airtable fails or returns nothing, the
    existing copy is kept.
  - `drop_inactive_drafts`.
  - The reviewer rules: `can_review`, `responsible_reviewers` and
    `reviewable_departments`.
  - `after_staff_sync`, which runs both the sync and the draft cleanup. It's
    registered with `user_service.register_post_sync_hook` in `main.py`, so
    the nightly sync and the manual sync both run it and `common` imports
    nothing from workforms.
- `workform_service.py`:
  - Validates entries and adds, edits and deletes them. Changes are refused
    with 400 if the month is closed and 409 if the workform is locked.
  - `combine` (Q15).
  - `submit`:
    1. Refresh the month from Airtable, then re-read the person's record.
    2. Refuse if any department has a decision.
    3. Create or patch the record. Only departments that already have
       values are cleared, since a department may not have all its columns.
    4. Save `submitted_blocks` and the LOA snapshot, and audit it.
- `review_service.py`:
  - `queue` and `pending_counts`.
  - `responsible_pending_count`, for the review email.
  - `default_month`.
  - `decide`: re-reads the record from Airtable, checks `can_review`,
    patches only `<Dept> : Approved`, and audits it. The queue refreshes a
    month from Airtable at most once a minute.
- `loa.py`: entry flags (Q24).
- `notifications.py`: `send_reminders` and `send_review_emails`, sent with
  `notification_service.send_email`, with each run written to `job_log`.

**Who reviews what**:

- A head reviews their departments' hours from everyone except themselves.
  Co-heads can review each other.
- An Operations head can review any department, including their own hours.
- `responsible_reviewers` decides whose review email counts a submission:
  - the department's heads other than the submitter, or
  - if there are none (a department with no head, or a sole head's own
    hours), the Operations heads.

### Routers (`app/workforms/routers/`)

Every route requires a login and Active status (`get_staff_member`, which
already honors impersonation). None is network-aware, so there's no guest
access, and `test_guest_access.py` passes unchanged. Workforms isn't a pass
giveaway router, so it doesn't need `GuestRedactingRoute`.

`workforms.py`, prefix `/api/workforms`:

- `GET /departments`: `{own, other}`.
- `GET /me`: open months, plus a summary of every month with a draft or
  submission.
- `GET /me/{YYYY-MM}`:
  - entries with LOA flags
  - status (`not_started` / `draft` / `submitted` / `locked`) and
    `has_unsent_changes`
  - deadline, `is_late` and `would_be_late`
  - each department's Airtable values and decision
- `POST /me/{month}/entries`, `PUT /me/{month}/entries/{id}`,
  `DELETE /me/{month}/entries/{id}`
- `POST /me/{month}/submit`
- `GET /preferences`, `PUT /preferences`

`review.py`, prefix `/api/workforms/review`, for department heads only
(403 otherwise):

- `GET ""`: own and fallback departments, `is_operations_head`,
  `default_month`, `default_department`, and the months that have
  submissions.
- `GET /{month}/pending`: undecided counts per department.
- `GET /{month}/{department}`: the queue, with `total`, `reviewed` and
  `remaining`.
- `PUT /decisions/{airtable_record_id}/{department}`: body
  `{decision: "Approved" | "Denied" | null}`.

`GET /api/users/me` gains `is_department_head`. `common` must not import
workforms, but `department_heads` is a shared model, so
`common/routers/users.py` queries the table directly.

### Scheduler (`app/scheduler.py`)

- The staff sync runs `after_staff_sync` through the post-sync hook. That
  syncs department heads and deletes unsubmitted drafts of staff who are no
  longer Active (Q20).
- `refresh_workform_records` runs at 2:30 AM Pacific every day (Q2). It's skipped when
  Airtable isn't configured.
- `send_workform_emails` runs at 9 AM Pacific every day, but only when
  `WORKFORMS_EMAILS_ENABLED` is set. It's off by default while the sub-site
  is under construction and not the official way to submit workforms:
  - `send_reminders` sends only on the last day of the month (for this
    month) and on the 3rd (for last month). It goes to Active staff who
    aren't heads, haven't submitted, and haven't opted out (Q27, Q28).
  - `send_review_emails` sends only on the 6th, to each head with
    undecided submissions they're responsible for.
- `bootstrap_workforms_if_empty` runs on startup. It syncs department heads
  if there's no copy yet, and refreshes the workforms copy.

### Tests (`backend/tests/workforms/`)

The Airtable client is mocked in every test. Tests cover:

- open months and the deadline boundary
- validation
- the combined text format
- create vs patch on submit, the locked check, and 0-hour workforms
- review permissions, including no-head departments, heads' own blocks, and
  Operations self-review
- decision changes and clearing
- LOA flags
- hand-edit detection
- the refresh deleting removed records
- department-head sync
- reminder recipients (submitted, 0-hour, heads, opted-out)
- the digest on the 6th
- impersonation acting as the impersonated head

## Frontend (`frontend/src/workforms/`)

- `subsites.ts`: add `{ basePath: '/workforms', name: 'KALX Workforms', … }`,
  available to the `promotions` and `staff` roles (Active), as the directory
  is. `App.tsx`: add it to `SUBSITE_APPS`.
- `WorkformsApp.tsx`: a `<BrowserRouter basename="/workforms">` with these
  routes:
  - `/` for this month
  - `/month/:month` for a specific month
  - `/history` for past workforms
  - `/review` and `/review/:month` for heads only
  - `/settings`
- `api.ts` / `types.ts`: `workformsAPI` and `reviewAPI`, using the `common`
  axios client.
- **Month page**:
  - Links switch between this month and last month, each with its status.
  - An "Add work" form has a department select (own departments first, then
    "Other departments"), hours (step 0.25), a date limited to the month and
    labeled "Date (recommended)", and a description. The department is kept
    for the next entry.
  - Entries are grouped into one card per department, dated entries first,
    each card with its total and the month total. Each entry can be edited or
    deleted in place.
  - Submit and Resubmit open an inline confirmation that summarizes the hours
    and warns about lateness and LOA overlap.
  - Notes show the deadline and the late, submitted, unsent-changes, locked
    and LOA states.
  - Once submitted, each department card shows its decision.
- **History page**: past months, each department's hours and decision
  (Approved / Denied / Pending), linking to the month page read-only.
- **Review page**:
  - A department selector, own departments first and fallback departments
    under a separate heading, and a month selector.
  - The person list shows decision status, Late badge and LOA badge.
  - The detail panel shows entries, the highlighted total, the Airtable
    values, and a hand-edit note when needed.
  - Buttons: Approve, Deny, Clear. A decision moves to the next pending
    person.
  - A progress bar reads "7 of 12 reviewed, 5 remaining".
- **Settings page**: one switch, either the reminder emails or the review
  emails, depending on `is_department_head`.
- Works on mobile. On small screens the review list and detail stack.
- Tests sit next to the files: validation helpers, the combine preview, the
  review progress and next-person logic, and the subsite availability.

## Docs and config

- `SECURITY.md`: workforms is listed among what guests can't reach, and the
  Airtable section notes the write access and the review rules.
- `CLAUDE.md`, which is gitignored and local only: the sub-site is added to
  the map tables and the route table.
- `apache/`: no change. `/api/` and the SPA fallback are generic.
- `.env.example`: the new settings. Production sets
  `AIRTABLE_WORKFORMS_TABLE_NAME=Workforms`.

## Airtable setup checklist

- The workforms table has Name (linked to "Online Staff App Directory"),
  Month (date), Created Time (created time), and the three
  "<Dept> : Hours/Description/Approved" columns for every department in
  "Department Heads".
- Set **"<Dept> : Hours" to show 2 decimal places**, so quarter hours aren't
  rounded. A rounded value looks like a hand edit in the review view.
- "<Dept> : Approved" has the options "Approved" and "Denied". The app sends
  `typecast`, so a missing option would be created rather than refused.
- The token (`AIRTABLE_API_KEY`) can read "Department Heads", and can read and
  write the workforms table.
