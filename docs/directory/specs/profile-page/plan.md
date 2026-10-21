# Implementation Plan: Directory Profile Page

## Overview

The KALX Staff Directory (`/directory/`) gets a **profile page**. Today "My
record" opens the same sidebar everyone else sees. The profile page replaces
that link with a full page that shows more about you than the sidebar does, and
lets you edit your own details.

The profile page has four parts:

- **Details**: the sidebar's fields, plus all leave dates, DJ Quiz years and
  Spinitron personas.
- **Edit form**: First Name, Surname, Pronouns, Phone, DJ Name and Photo. The
  app can only read Airtable today, so the form is built in full, including the
  backend write path, but switched off by a config flag. Turning editing on
  needs Airtable write access and the flag, and no new code.
- **Sublist DJ eligibility checklist**: whether you meet each requirement for
  subbing a DJ shift, with the evidence behind each answer and the date you stay
  eligible until.
- **Workforms summary**: your last 12 months of workforms.

Only the person themselves and site admins can see a profile.

To recognize specialty shows in the Spinitron playlist log, the pass giveaway's
specialty shows also gain Spinitron show IDs and a **retired** state. Site
admins can also view someone else's workforms in `/workforms/`.

Terms:

- **Persona**: a Spinitron DJ identity (`/KALX/dj/<id>/`). A staff member's
  personas come from Airtable's "DJ Name" field.
- **Placeholder persona**: a shared persona that isn't one person
  (`SPINITRON_PLACEHOLDER_PERSONA_IDS`: DJ Trainee, KALX Overnights, Rotating
  Dj, and so on).
- **Quarter**: KALX's quarters are offset by a month: Feb–Apr, May–Jul, Aug–Oct
  and Nov–Jan (Nov–Jan crosses the new year). Months are in America/Los_Angeles.
- **Shift**: one or more back-to-back Spinitron playlists treated as one block
  of airtime (see Q9).

## Agreed decisions (from grilling session, 2026-10-20)

| # | Decision |
|---|----------|
| Q1 | Your own profile is at `/directory/me`. "My record" becomes "My profile" and links there. Clicking your own row in the list still opens the normal sidebar, so you can see what others see. |
| Q2 | The profile adds the eligibility checklist and a workforms summary. LOA dates, DJ Quiz years and personas linked to Spinitron appear on both the sidebar and the profile (the sidebar's LOA rule is unchanged, see Q20). |
| Q3 | First Name, Surname, Pronouns, Phone, DJ Name and Photo are editable but disabled for now. Everything else (Email, Departments, Status, Titles and Roles, LOA dates, DJ Quiz) is plain read-only text. |
| Q4 | The whole write path is built now: the endpoints, validation, the Airtable write, a re-sync of the record and audit logging. Tests run against a mocked Airtable, and a config flag gates it all. |
| Q5 | The DJ Name editor shows personas as chips. You add one from a type-ahead over known Spinitron personas, or by pasting a Spinitron persona URL into the same box. Placeholder personas are left out of the type-ahead and refused when pasted. Role personas such as "Sports Staff" are shared, but they aren't linked to anyone's DJ Name, so there's no special handling for personas linked to someone else. |
| Q6 | The checklist is shown to anyone with a Spinitron persona or the "Sublist DJ" status. |
| Q7 | Besides the four requirements, the checklist checks "Not on leave of absence". There's no Active-versus-🆕 check. |
| Q8 | The shift requirement uses the **previous complete quarter**. |
| Q9 | A qualifying shift is a Spinitron playlist whose persona is one of yours, lasting at least 90 minutes (end minus start), and not a specialty show. A playlist is a specialty show when its `show_id` is one of a specialty show's Spinitron show IDs (Q15). A show's title says nothing either way, because FREEFORM is only the default title and most regular shows are named by their DJ. Back-to-back playlists count as one shift. Placeholder personas never count. |
| Q10 | The roboshow alternative (submitting a 2-hour recording) has no data source. The checklist explains it in the shift requirement's details. Shift sources are pluggable, so a roboshow source can be added later. |
| Q11 | The workforms requirement uses the last 3 complete months: 6 h each (`REQUIRED_MONTHLY_HOURS`). Months that overlap a leave of absence count as met. Earlier months will be imported, so every month has data. |
| Q12 | The DJ Quiz deadline is set per year in KALX Staff Admin. |
| Q13 | The checklist shows a summary at the top, one ✓/✗ row per requirement with a one-line status, and an expandable details section per row with the full rule and its evidence. It also shows "Eligible until <date>". |
| Q14 | The checklist and the workforms summary are visible to the person and to all site admins, and nobody else. |
| Q15 | Specialty shows get Spinitron show IDs, set by pasting a Spinitron URL, and the ID is required when a show is created. Playlists are matched to specialty shows by `show_id`. |
| Q16 | Site admins open anyone's profile at `/directory/:staffId/profile`. The sidebar shows site admins a "View full profile" link. The backend returns 403 to anyone who is neither that person nor a site admin. Once editing is on, Active Paid Staff can edit other people's profiles too; other site admins can only see them. Viewing a profile isn't audit-logged. |
| Q17 | For the two older months, a department's hours count only if it Approved them. A department that hasn't decided yet makes the month ✗, with "awaiting <Dept>". For the most recent month, a department's decision counts where there is one (Denied hours drop out), and submitted hours count where there isn't. |
| Q18 | The workforms summary covers the last 12 months, one row each: month, hours reported, hours approved, status (draft, submitted, late, LOA) and a link to that month in `/workforms/`. It's shown whether or not the person is a DJ. Site admins see it on other people's profiles, and its links take them to that person's workforms (Q29). |
| Q19 | While editing is off, the form says: "Editing isn't available here yet. To update these details, fill out this form: https://docs.google.com/forms/d/e/1FAIpQLSf7IIE8IrSPqODgGCLB1MZvFe2OlyCxfCHRYbSS5cGVs_QfQg/viewform" |
| Q20 | The sidebar's leave rule doesn't change: it shows current or upcoming leave, or the On leave status. The profile always shows the leave dates, including a past leave. |
| Q21 | The DJ Quiz deadlines are seeded with 2025 → Jul 31 and 2026 → Sep 30. A deadline means 23:59:59 Pacific on that date. Only site admins can edit the deadlines, in a "DJ Quiz deadlines" section of KALX Staff Admin, and each change is audit-logged. |
| Q22 | "Eligible until" is the earliest of: the end of the quarter your latest qualifying shift makes you eligible for, this year's quiz deadline if you haven't done this year's quiz, and the start of an upcoming leave. The workforms requirement isn't counted in it. A separate line says which month's workform counts next, for example "October's workform counts from November 1". |
| Q23 | A nightly job, listed in KALX Staff Admin, stores the previous and current quarter's playlists. The profile shows "Shifts as of <time>". |
| Q24 | This spec goes in `docs/directory/specs/profile-page/plan.md`, and all of the work ships in one PR. |
| Q25 | A Spinitron show URL (`…/KALX/show/<id>/…`) or playlist URL (`…/KALX/pl/<id>/…`) is accepted, on `spinitron.com` or `widgets.spinitron.com`. For a playlist URL, the app looks up the playlist's show when the form is saved. The form shows the title of the show it resolved to. |
| Q26 | A specialty show can have several Spinitron show IDs. Specialty shows can also be **retired**: a retired show is kept, but the pass giveaway no longer treats it as a current specialty show. |
| Q27 | Existing specialty shows start with no IDs. Saving any edit to one requires at least one ID, and the specialty shows page warns about shows without one. Until a show has an ID, its playlists can count as qualifying shifts. That gap is accepted, and the IDs will be filled in right after deploying. |
| Q28 | The directory gets specialty show IDs (and workforms hours) through provider hooks in `common`, which the sub-sites that own the data register from `main.py`. Sub-sites still never import each other. |
| Q29 | `/workforms/` gets new view-only pages for site admins: another person's month (the MonthPage layout with a "Viewing <name>'s workform" banner) and their history, with new endpoints that take a staff ID. |
| Q30 | When Paid Staff edit someone else's profile, it's audit-logged. The person isn't emailed. |
| Q31 | Photo upload is built now, behind the same flag. It accepts JPEG or PNG up to 5 MB, and the new photo replaces the current one. There's no cropping: the photo sync already makes the square thumbnail. |
| Q32 | Validation: First Name is required, and Surname is optional. Pronouns are free text, up to 40 characters. Phone is optional; if given, it must be a US 10-digit number, saved in the format `formatPhone` displays. DJ Name can have zero or more personas, and placeholder personas are refused. |
| Q33 | **Retired** is separate from the existing **deleted** flag. Deleted is for mistakes, so its Spinitron IDs are ignored. A retired show's IDs still mark its playlists as specialty. |
| Q34 | A retired show can't be pre-assigned passes and isn't offered in DJ name or show suggestions. It's listed in a collapsed "Retired shows" section with an "Un-retire" button. Passes already assigned to it stay as they are. Anyone who can edit a specialty show can retire or un-retire it, and both are audit-logged. Retired shows still need Spinitron IDs and appear in Q27's warning. |
| Q35 | Spinitron marks roboshows `automation: 1`, but doesn't record who submitted them, so they can't satisfy the shift requirement. Playlists with `automation` set never count as a qualifying shift, and never join a back-to-back merge. The roboshow route stays as Q10 describes. |

## Sublist DJ eligibility rules

These rules are computed on the backend in `directory/services/eligibility.py`,
from data stored locally. Rendering the checklist never calls Spinitron or
Airtable.

| Requirement | Met when | One-line status | Details |
|---|---|---|---|
| Sublist DJ status | Status includes `Sublist DJ` | "On the DJ sublist" / "Not on the DJ sublist" | What the sublist is and who manages it |
| Not on leave | Not `on_leave(staff, today)`, and no On leave status | "Not on leave" / "On leave until <date>" | Leave dates |
| Shift last quarter | At least one qualifying shift that started in the previous complete quarter | "Last qualifying shift: <date>, <title>, <h:mm>" / "No qualifying shift in <May–Jul 2026>" | The rule (90 min, own persona, not specialty, not automated, back-to-back merged); every playlist found under your personas in the previous and current quarter, each marked counted or not with the reason (too short, specialty show <name>, automated); the roboshow note (Q10); "Shifts as of <time>" |
| Workforms, last 3 months | Each of the 3 complete months is met (Q11, Q17) | "Jul 6 h ✓, Aug 4.5 h ✗, Sep 7 h ✓" | One line per month: approved / submitted hours per department, pending departments named, LOA months marked, a link to the month |
| DJ Quiz | You've done the **current quiz year** | "2026 quiz done" / "2026 quiz due Sep 30, 2026" | The rule, your quiz years, the current deadline |

**Shifts.** The playlists considered are those whose `persona_id` is one of the
person's personas and isn't a placeholder. A playlist is excluded if
`automation` is set or its `show_id` is a specialty show ID. The remaining
playlists, sorted by start, are merged into one shift whenever one's `end`
equals the next one's `start`. A shift qualifies at 90 minutes or more, and it
belongs to the quarter its first playlist started in, in Pacific time.

**Current quiz year.** Let Y be this year. If Y has a deadline and now is past
it, the current quiz year is Y. Otherwise it's Y − 1, so last year's quiz still
counts until this year's deadline. If Y has no deadline yet, the details say "The
<Y> quiz deadline hasn't been announced."

**Overall.** You're eligible when every row is ✓. The summary reads "✅
Eligible to sub" or "❌ Not eligible yet: N of 5 requirements unmet".

**Eligible until** (only shown when eligible). The earliest of:

- The end of the quarter your shift makes you eligible for. A shift in the
  previous quarter covers the current quarter. If you also have a shift in the
  current quarter, you're covered through the end of the next quarter.
- This year's quiz deadline, if it's still ahead and you haven't done this
  year's quiz.
- The day before an upcoming leave starts.

Under the date, a separate line notes the next workforms month to count (Q22).

## Airtable

**Online Staff App Directory** (`AIRTABLE_TABLE_NAME`):

| Field | Type | App use |
|---|---|---|
| First Name, Surname | Text | read; written by profile edit |
| Pronouns | Text | read; written by profile edit |
| Phone | Phone/text | read; written by profile edit |
| DJ Name | Long text (Markdown links) | read; written as `[Name](https://spinitron.com/KALX/dj/<id>/)` links joined with `, `, matching what the sync parses today |
| Photo | Attachment | read; written by photo upload |
| DJ Quiz | Multi-select of years (`2025`, `2026`, …) | **new**: read by the sync into `staff.dj_quiz_years` |

**Writes** go to the staff member's record (`staff.airtable_record_id`) with a
`PATCH` to the table. They need a token with write access to this table, which
the current `AIRTABLE_API_KEY` doesn't have.

**Photo** uploads use Airtable's `uploadAttachment` endpoint
(`content.airtable.com/v0/{base}/{record}/Photo/uploadAttachment`), which takes
base64 data up to 5 MB and adds the file to the field. Then a `PATCH` sets
Photo to only the new attachment, so it replaces the old one.

After any write, the app re-syncs that one record, so the directory reflects the
change at once.

## Spinitron

The API reference is
https://raw.githubusercontent.com/spinitron/v2api/refs/heads/master/docs/spinitron.json.

- `/playlists?start=&end=` returns items with `id`, `persona_id`, `show_id`,
  `start`, `end`, `duration`, `title` and `automation`. Add `show_id` and
  `automation` to the parsed item (`SpinitronShowItem`, or a new
  `SpinitronPlaylistItem` if adding them to the shared one clutters its other
  callers).
- `/playlists/{id}` resolves a pasted playlist URL to its `show_id` (Q25).
- `/shows/{id}` gets a show's title, to confirm a pasted URL.
- `/personas`: `fetch_all_personas()` already returns `{id: name}`, which the
  persona type-ahead uses, cached through `cache_service`.

## Backend

### Config (`app/config.py`)

- `directory_self_edit_enabled: bool = False` (Q4). Add it to `.env.example`.
  Production and staging leave it off until the token can write.

### Audit areas (`app/common/areas.py`)

- Add `DIRECTORY_AREA = "KALX Staff Directory"` to `AREAS`. Profile edits, photo
  uploads and quiz deadline changes log under it. Specialty show retire and
  un-retire log under `PASS_GIVEAWAY_AREA`.

### Models (`app/models/`, one Alembic migration)

- `staff.dj_quiz_years` (JSON list of ints, nullable). Airtable: "DJ Quiz".
- `dj_quiz_deadlines` (directory): `year` (int, PK), `deadline` (date),
  `updated_at`. Seeded with 2025-07-31 and 2026-09-30 (Q21).
- `dj_shift_playlists` (directory): `id` (Spinitron playlist id, PK),
  `persona_id`, `show_id`, `start`, `end`, `title`, `automation` (bool),
  `fetched_at`. This is separate from the pass giveaway's `spinitron_playlists`
  cache, which has a different window and purpose and is owned by another
  sub-site.
- `specialty_show_spinitron_shows` (pass giveaway): `id`, `specialty_show_id`
  (FK, cascade delete), `spinitron_show_id` (unique), `title` (the Spinitron
  show title when it was added).
- `specialty_shows.retired_at` (datetime, nullable). Null means current.

Update the model list in CLAUDE.md: the two `dj_*` tables belong to the
directory. `specialty_show_spinitron_shows` belongs to the pass giveaway.

### Common (`app/common/`)

- `services/user_service.py`:
  - Sync "DJ Quiz" into `dj_quiz_years`, keeping only values that are years.
  - Add `sync_one(db, airtable_record_id)`, which fetches one record and applies
    the same per-record logic as the full sync, including the photo.
  - Add `airtable_update_staff(record_id, fields)` and
    `airtable_upload_photo(record_id, filename, content_type, data)`. If
    another write function already exists, this can live in a small
    `airtable_write.py` next to it.
- `services/profile_providers.py`: registries filled from `main.py`, so the
  directory reads other sub-sites' data without importing them (Q28):
  - `register_specialty_show_ids_provider(fn)`, where
    `fn(db) -> set[int]` returns the Spinitron show IDs of every specialty show
    that isn't deleted, retired ones included (Q33).
  - `register_monthly_hours_provider(fn)`, where
    `fn(db, staff, months) -> dict[date, MonthHours]`. `MonthHours` is defined
    in common: per department, the hours, decision and whether it was
    submitted; whether the month overlaps a leave; the workform status; and
    whether it was late.
  - If a provider isn't registered, the directory shows that requirement as
    "unavailable". In tests it is always registered.

### Directory (`app/directory/`)

- `schemas/directory.py`:
  - `DirectoryEntry` gains `dj_quiz_years: list[int]`.
  - `DjPersona` gains a `url` field (or the frontend builds the URL from the
    `id`).
  - New `ProfileResponse`: the entry, plus the editable values as Airtable holds them
    (`first_name`, `surname`, `pronouns`, `phone`), the full `loa_start`/`loa_end`,
    `can_edit` (flag on, and the viewer is that person or Paid Staff),
    `is_self`, `eligibility` (or null when Q6 doesn't apply) and
    `workforms` (12 `MonthSummary` rows).
  - New `ProfileUpdate`, with Q32's validation.
  - New `EligibilityResponse`, with rows, the summary, `eligible_until`,
    `next_workform_note` and `shifts_as_of`.
- `services/eligibility.py`: the rules above, as pure functions over the
  playlists, provider results, staff and today's date, so they can be tested
  without a database. Quarter helpers (`quarter_of`, `previous_quarter`,
  `quarter_end`) go here too.
- `services/shift_sync.py`: fetches the previous and current quarter's
  playlists and replaces the rows in that window in `dj_shift_playlists`.
- `services/profile_edit.py`: validates an update, converts DJ Name personas to
  the Airtable Markdown, writes to Airtable, calls `sync_one`, and logs which
  fields changed (old and new values, except the photo) to `audit_log` with
  `area=DIRECTORY_AREA`.
- `jobs.py`: `ADMIN_JOBS` with "Sync DJ shifts from Spinitron"
  (`dj_shift_sync`), registered from `main.py`. Scheduled nightly in
  `scheduler.py`.
- `routers/directory.py` (all endpoints require a login, through
  `get_staff_member` or `get_site_admin`):
  - `GET /api/directory/me/profile` and `GET /api/directory/{staff_id}/profile`:
    403 unless the viewer is that person or a site admin (`is_site_admin`
    checks the real signed-in user). 404 if the person isn't current staff.
  - `PATCH /api/directory/{staff_id}/profile`: 403 unless the viewer is that
    person or Active Paid Staff (`is_paid_staff`, real signed-in user). 403 with
    "Editing isn't available yet" when the flag is off. Returns the new
    `ProfileResponse`.
  - `POST /api/directory/{staff_id}/photo` (multipart): same access check
    and flag. JPEG or PNG only, 5 MB maximum.
  - `GET /api/directory/personas?q=`: the persona type-ahead, without
    placeholders, up to 20 results.
  - `POST /api/directory/personas/resolve` `{url}`: returns the persona for a
    pasted `…/KALX/dj/<id>/…` URL, or 400.
- `routers/admin.py` (prefix `/api/directory/admin`, site admins):
  `GET /dj-quiz-deadlines`, `PUT /dj-quiz-deadlines/{year}` `{deadline}` and
  `DELETE /dj-quiz-deadlines/{year}`, each audit-logged.

### Pass giveaway (`app/pass_giveaway/`)

- Schemas: `SpecialtyShowCreate` takes `spinitron_urls: list[str]` (at least
  one). `SpecialtyShowUpdate` takes `spinitron_urls: list[str] | None`, and
  saving fails if the show would have none. `SpecialtyShowResponse` gains
  `spinitron_shows: [{id, title, url}]` and `retired: bool`.
- `services/specialty_show_spinitron.py`: parses show and playlist URLs,
  resolves a playlist to its show, fetches the show title, and refuses an ID
  that already belongs to another show.
- `routers/specialty_shows.py`:
  - Create and update accept the URLs.
  - New `POST /{id}/retire` and `POST /{id}/unretire`, for Promotions staff or
    a show owner, the same people who can edit.
  - The existing list endpoints, which feed pass assignment and suggestions,
    leave out retired shows (Q34). A new
    `GET /api/specialty-shows?include_retired=true`, or a separate
    `/retired` endpoint, feeds the collapsed section.
  - Every query that offers specialty shows for assigning passes or for DJ name
    and show suggestions filters on `retired_at IS NULL`, in `pass_service.py`
    and in the Spinitron title services.
- Register `specialty_show_ids_provider` from `main.py`.
- Every route keeps `route_class=GuestRedactingRoute`.

### Workforms (`app/workforms/`)

- Register `monthly_hours_provider` from `main.py`, built from
  `workform_airtable_records` (decisions, submitted hours), `workforms`
  (draft status) and `loa.month_overlaps`.
- `routers/workforms.py`, for site admins only (Q29):
  `GET /api/workforms/staff/{staff_id}` (history, the same shape as `/me`)
  and `GET /api/workforms/staff/{staff_id}/{month}` (the same shape as
  `/me/{month}`, read-only). Factor the `/me` handlers so both share one
  builder.

### Tests

- `tests/directory/`:
  - Profile access: self, site admin, another staff member (403), impersonation
    (the real user decides).
  - Edits with the flag off (403) and on, against a mocked Airtable: field
    mapping, DJ Name Markdown, validation errors, the audit entry, `sync_one`
    being called.
  - Photo type and size limits.
  - Persona type-ahead and resolve, with placeholders excluded.
  - Quiz deadline admin endpoints.
- `tests/directory/test_eligibility.py` (pure functions):
  - Quarter boundaries, including Nov–Jan across the year.
  - The 90-minute boundary.
  - Back-to-back merging, and a specialty or automated playlist breaking a
    merge.
  - Placeholder personas.
  - Unregistered specialty IDs.
  - Workforms: approved, denied, pending, the most recent month, LOA.
  - The quiz year before and after the deadline, and a missing deadline.
  - Every term of "eligible until".
- `tests/pass_giveaway/`:
  - Spinitron URL parsing and resolving (mocked).
  - Duplicate IDs.
  - Requiring an ID on create and edit.
  - Retire and un-retire: permissions, the audit entry, and exclusion from
    assignment and suggestions.
  - The provider includes retired shows and leaves out deleted ones.
- `tests/workforms/`: the site admin staff endpoints (403 for others) and the
  hours provider.
- `tests/common/`: the DJ Quiz sync, `sync_one`, and the guest access allowlist
  still passing with the new routes.

## Frontend

### Directory (`frontend/src/directory/`)

- `DirectoryApp.tsx`: add the routes `/me` and `/:staffId/profile`, both
  rendering `ProfilePage`, placed before `/:staffId`.
- `DirectoryPage.tsx`:
  - "My record" becomes "My profile", linking to `/me`.
  - `DirectoryDetail.tsx` adds DJ Quiz years and persona links to Spinitron.
  - Site admins get a "View full profile" link.
- `ProfilePage.tsx`: the details, the edit form, the eligibility checklist
  (when present) and the workforms summary. The page title is "My profile" or
  "<name>'s profile".
- `ProfileEditForm.tsx`:
  - The fields from Q3.
  - When `can_edit` is false, every input and the Save button are `disabled`,
    and the Q19 note is shown. That note's text is a constant in this file.
  - When `can_edit` is true, saving sends the `PATCH` and shows the validation
    errors.
  - The photo control is a file input with a preview.
- `DjPersonaEditor.tsx`:
  - Chips with remove buttons.
  - One input that is both a type-ahead (`/personas?q=`) and the place to paste
    a URL (`/personas/resolve`).
  - Disabled together with the rest of the form.
- `EligibilityChecklist.tsx`:
  - The summary.
  - One `<details>` row per requirement, with ✓/✗ icons that also carry text,
    so the result doesn't rely on color alone.
  - "Eligible until" and the next-workform line.
  - "Shifts as of".
- `WorkformsSummary.tsx`:
  - A 12-row table.
  - The links go to `/workforms/month/<YYYY-MM>` for yourself, or to
    `/workforms/staff/<id>/month/<YYYY-MM>` for someone else. They're plain
    `<a href>` links, since they cross sub-sites.
- `api.ts`: `getProfile`, `updateProfile`, `uploadPhoto`, `searchPersonas`,
  `resolvePersona`. `types.ts`: the matching types.

### Pass giveaway (`frontend/src/pass-giveaway/`)

- Specialty show create and edit (`staff/SpecialtyShowDetail.tsx` and the
  create form):
  - A list of Spinitron show URLs, each shown with its resolved title and a
    remove button.
  - At least one URL is required.
- `staff/SpecialtyShowList.tsx`:
  - A warning lists the shows that have no Spinitron ID.
  - A collapsed "Retired shows" section, with Retire and Un-retire buttons.
- Assignment and suggestion UIs need no change beyond the backend filter.

### Workforms (`frontend/src/workforms/`)

- `WorkformsApp.tsx`: add the routes `/staff/:staffId` (history) and
  `/staff/:staffId/month/:month` (month), guarded to site admins.
- Reuse `MonthPage` and `HistoryPage` in a read-only mode (no add, edit or
  submit controls) with a "Viewing <name>'s workform" banner, rather than
  copying them.

### Admin (`frontend/src/admin/`)

- `DjQuizDeadlinesSection.tsx` (site admins): a list of the years and their
  deadlines, with add, edit and remove. `api.ts` calls
  `/api/directory/admin/dj-quiz-deadlines`.

### Tests

Next to each new component, following CLAUDE.md's rule that a test must not end
while anything is pending (no act() warnings):

- The profile page renders for self and for a site admin, and the fields are
  disabled when `can_edit` is false.
- Persona chips: adding and pasting.
- The checklist's states and its expandable details.
- The summary links.
- The specialty show URL list, and retire and un-retire.
- The workforms read-only mode.
- The quiz deadlines section.

## Docs and config

- CLAUDE.md:
  - The directory routes and files.
  - The new tables and who owns them.
  - `profile_providers` beside `register_post_sync_hook`.
  - `DIRECTORY_AREA`.
  - The workforms staff routes.
  - The KALX Staff Admin sections.
- `SECURITY.md`: profiles, the checklist and workforms are visible to the
  person and to site admins only.
- `.env.example`: `DIRECTORY_SELF_EDIT_ENABLED`.
- `backend/app/config.py`: the comment on `spinitron_non_dj_show_titles` now
  says FREEFORM is only the default title (already done).

## Rollout checklist

1. Add the "DJ Quiz" multi-select to the Online Staff App Directory table
   (already done), then deploy and run the staff sync.
2. After deploying, add Spinitron show URLs to every specialty show, retired
   ones included (Q27), and retire the shows that have ended.
3. Run "Sync DJ shifts from Spinitron" once from KALX Staff Admin, rather than
   waiting for the nightly run.
4. Check the DJ Quiz deadlines in KALX Staff Admin.
5. Later, to turn editing on: give `AIRTABLE_API_KEY` (or a separate write token)
   write access to the Online Staff App Directory table, and set
   `DIRECTORY_SELF_EDIT_ENABLED=true`.
