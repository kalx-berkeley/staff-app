# Implementation Plan: KALX Staff Analytics

## Overview

A new sub-site, **KALX Staff Analytics** (`/analytics/`), shows metrics about
the staff app. It starts with the Radio Pass Giveaway and Short Links, and is
built so that other sub-sites can add their own metrics later.

Every page has a shared time-window control, and every metric has an ⓘ
popover that explains exactly how it's calculated.

Some metrics use data the app already stores (shows, passes, winners,
attempts, the audit log). Others need **new tracking**, which starts collecting
on the day this ships: signed-in visits, DJ studio and station office guest
sessions, "I'm off the mic" page visits, spin-match popups and `/go/`
redirects.

Terms:

- **On-air utilization**: pass pairs given away ÷ pass pairs.
- **Staff utilization**: staff passes claimed ÷ staff passes.
- **Owner**: the KALX promotions reps of a show's `promoted_by` (its promoter,
  or the venue when it has no promoter).
- **Creator**: the actor of the show's `show_created` audit log entry.
- **Giveaway page**: the "I'm off the mic" page, `/pass-giveaway/dj/shows/:id/giveaway`.
- **Normalized phone**: digits only, with a leading US `1` dropped from 11-digit numbers.
- **Normalized name**: lowercased, punctuation removed, runs of whitespace
  collapsed to one space, trimmed. DJ names use the same rule.
- Dates and calendar windows are in America/Los_Angeles.

## Agreed decisions (from grilling session, 2026-11-08)

| # | Decision |
|---|----------|
| Q1 | The sub-site is `/analytics/`, named "KALX Staff Analytics", with code name `analytics`. It gets a home page card for the people who can use it. |
| Q2 | Access is set once for the whole sub-site: site admins and Promotions admins (`auth.get_site_or_promotions_admin`), checked against the real signed-in user. It isn't open to guests. |
| Q3 | Show-level metrics (frequency, utilization, pre-assign %, monthly rep report) place a show by its **show date**. Activity metrics (visits, attempts vs. giveaways, `/go/` clicks, DJ rankings) use **when the event happened**. Each tooltip says which date it uses. |
| Q4 | Utilization metrics count only shows that are closed or whose show date has passed. Count metrics (such as show frequency) count all published and closed shows. Draft and deleted shows are always excluded. |
| Q5 | New tracking goes into one generic `analytics_event` table. |
| Q6 | Raw events are kept for 13 months. A scheduled job, listed in KALX Staff Admin, rolls older events into daily counts per type, entity, actor and dimension, then deletes the raw rows. |
| Q7 | Presets: last 30 days (the default), last month, this quarter, last quarter, this year, last year and all time, plus a custom from–to range. Quarters are calendar quarters. The chosen window goes in the URL. |
| Q8 | Metrics are computed with live SQL on each request. |
| Q9 | Charts use Recharts, loaded only in the analytics chunk. Every chart has a table view with the exact numbers. |
| Q10 | Repeat winners are grouped by normalized phone. Each row shows the most recent name, the real phone number, the win count, and the venues and dates. |
| Q11 | Legacy-imported data is included or excluded per metric, whichever is simpler. It doesn't need special handling. |
| Q12 | **Utilization balance** = on-air utilization % − staff utilization %, in percentage points. It's shown as a diverging bar centered on 0. A venue with fewer than 3 shows in the window is flagged "low sample" and isn't ranked. |
| Q13/Q26 | A giveaway page visit belongs to the name in the DJ name field at the top of the page (`DjNameInput`). If a pass is given away or "tried" is clicked, the name sent with it wins. If the field is blank, the visit belongs to "Unknown DJ". |
| Q14 | DJ names are matched after normalizing for case and whitespace, with no alias merging. |
| Q15 | A visit is one load of the giveaway page in a tab. Reloading in the same tab within 10 minutes continues the same visit. The outcome is the best one in the visit: given away > tried > neither. Per-venue funnels group the same visits by the show's venue. |
| Q16 | Signed-in usage is measured as **active days**: one per user per sub-site per day, recorded on the first page load that day. The page shows daily, weekly and monthly distinct users, a per-sub-site breakdown, and a per-user table (active days, last seen). |
| Q17 | DJ studio network and station office network guests are measured as **sessions**: one per tab, ending after 30 minutes idle. They're shown as two separate series, with sessions per day and an hour-of-week heatmap. |
| Q18 | Nothing is tracked while a site admin is impersonating someone. Tracking runs on staging as well as production. |
| Q19 | Spin-match popups are recorded as "suggested" the first time any DJ client receives a (spin, show) match, deduplicated on the server. The dismiss endpoint records whether the DJ dismissed or clicked through. The metric shows suggested, clicked through, dismissed and ignored counts, plus passes given away for that show within 2 hours of the spin. |
| Q20 | The monthly Promotions reps report has one row per **creator**, counting their published and closed shows dated in that month. Clicking a name lists those shows, each with its owners, and highlights a show whose creator isn't one of its owners. Shows without a `show_created` entry are listed under "Unknown creator". |
| Q21 | Each venue lists who created its shows, marking each creator as a venue owner, the show's promoter owner, or neither. Only "neither" is flagged. |
| Q22 | `/go/` redirects are tracked with their result (redirected, blocked as not staff, blocked on the DJ network). The report shows counts and unique users, never names. KALX Staff Admin's short links list gets a "Clicks (30 days)" column that links to analytics. |
| Q23 | The tabs are Overview, Venues (table, then a venue page), DJs (table, then a DJ page), Promotions reps, Short links and Site usage. The time-window control sits in a shared header and applies to every tab. |
| Q24 | The backend sends each metric's explanation with the metric, so the text sits next to the SQL. |
| Q25/Q31 | The extra v1 metrics are lead time, passes unused at close, lottery oversubscription, the alternate list (per venue), utilization by weekday and show time, utilization per promoter, staff pass reach, win-limit warnings and overrides, the repeat winner share, and time to first giveaway (definitions below). There are no genre metrics and no backlog. |
| Q27 | No genre-based metrics. |
| Q28 | Staff pass reach uses **today's** Active staff as the denominator. |
| Q29 | Top lists show 10 rows with "Show all". DJs and venues with fewer than 3 shows or visits in the window are flagged "low sample" and left out of rankings. |
| Q30 | Everything ships in one PR, on the `analytics` branch. |
| Q32 | This spec lives at `docs/analytics/specs/analytics-site/plan.md`. |
| Q33 | **Same name, different phones**: names are matched exactly after normalizing (case, spaces, punctuation). There's no fuzzy matching. |
| Q34 | A name appears when it has at least one on-air win in the window, and it's compared against all of that name's wins at any time. |
| Q35 | It's shown both globally and per venue. A name is **flagged** when it has two or more different phones at the same venue within that venue's `win_frequency_days`. Venues with no limit never flag. |
| Q36 | When the same email appears under different phones, it's shown as stronger evidence. There's no "ignore" marking in v1. |

## Metrics

Each metric has an ID, a title, a value (or rows or series) and an
`explanation` object: `{formula, date_basis, includes, excludes, data_since}`.
`data_since` is set for tracked metrics: the earliest event of that type, so
the tooltip can say "Tracked since Nov 12, 2026".

### Shared definitions

- **Shows in scope**: status `published` or `closed`, with the show date in
  the window.
- **Completed shows** (for utilization): shows in scope that are `closed` or
  whose show date is before today.
- **Pass pairs**: `passes.pass_type = 'pair'`. **Given away**: `status = 'given_away'`.
- **Staff passes**: `show.num_staff_passes` per show. **Claimed**: staff-type
  passes with `status = 'claimed'`. Check during implementation whether guest
  holds (`guest_of_pass_id` set) are counted within `num_staff_passes`, and
  count them consistently on both sides of the ratio. The tooltip says how
  guest seats are counted.
- **DJ**: normalized DJ name. It's shown as the most common original spelling.

### Per venue (Venues tab and venue page)

| Metric | Definition |
|---|---|
| Show frequency | Shows in scope; also shows per month, as a chart. |
| On-air utilization | Given-away pairs ÷ pairs, over completed shows. |
| Staff utilization | Claimed staff passes ÷ staff passes, over completed shows. |
| Utilization balance | On-air % − staff %, in percentage points (Q12). |
| Attempts vs. giveaways | `show_attempts` count vs. pairs given away, by event time; shown as attempts per giveaway. |
| Pre-assigned % | Pairs with `preassigned_dj` set ÷ pairs, over shows in scope. |
| Top repeat winners | As in the global list, filtered to the venue's shows. |
| Same name, different phones | As in the global list, filtered to the venue (Q35). |
| Who posts shows | Creators of shows in scope with counts, each marked venue owner / promoter owner / neither (Q21). Shows the venue's current owners alongside. |
| Giveaway page funnel | Visits to giveaway pages for the venue's shows: % given away, % tried, % neither (Q15). |
| Lead time | Median days from `published_at` to show date. Also utilization by lead-time bucket: <7, 7–14, 15–30, >30 days. |
| Unused at close | Pairs and staff passes still `available` on completed shows. |
| Lottery oversubscription | For lottery shows: lottery entries ÷ staff passes, and % of lottery shows where entries exceeded staff passes. |
| Alternate list | From `alternate_*` audit events for the venue's shows: people who joined, people who later got a pass (`alternate_promoted`), and conversion %. Per venue only, not per show. |
| Win-limit warnings and overrides | Counts of `winner_frequency_warning` and `venue_frequency_override` audit events, by event time. |
| Time to first giveaway | Median hours from `published_at` to the show's first `given_away_at`. |

The Venues tab table shows show count, on-air %, staff %, balance and
attempts per giveaway, sortable. Each row links to the venue page.

### Per DJ (DJs tab and DJ page)

| Metric | Definition |
|---|---|
| Giveaway page funnel | The DJ's visits (Q13): % given away, % tried, % neither. "Unknown DJ" is a row of its own. |
| Passes given away | Pairs given away by the DJ (`given_away_by_dj`), by `given_away_at`. |
| Attempts | `show_attempts` by the DJ, by `attempted_at`. |

### Global (Overview tab)

| Metric | Definition |
|---|---|
| Top repeat winners | Grouped by normalized phone, with at least one win in the window and 2+ wins in the window. Columns: latest name, phone, wins, venues, dates. |
| Repeat winner share | On-air wins in the window that went to a phone with more than one win at any time ÷ on-air wins in the window. |
| Same name, different phones | Normalized names with a win in the window and 2+ distinct normalized phones over all time. Each phone is listed with its wins (date, show, venue, DJ, email). The row is flagged when two of the phones won at the same venue within its `win_frequency_days`. A matching email across phones is shown as "same email". |
| Top DJs by passes given away | Pairs given away per DJ, by `given_away_at`. |
| Top DJs by given away + tried | Given away plus `show_attempts`, per DJ. |
| Top venues by utilization | Three rankings: on-air, staff and combined ((given-away pairs + claimed staff passes) ÷ (pairs + staff passes)). Low-sample venues are excluded (Q29). |
| Spin-match suggestions | Suggested, clicked through, dismissed and ignored (suggested with neither). Passes given away for the matched show within 2 hours of the spin's time. |
| Utilization by weekday and show time | On-air and staff utilization by the show's weekday, and by start time: before 6pm, 6–9pm, after 9pm, unknown. |
| Utilization per promoter | The same on-air, staff and balance metrics as venues, for shows with a `promoter_id`. Shown in its own table. |
| Staff pass reach | Active staff (status "Active" today) with at least one claim in the window (by `claimed_at`) ÷ Active staff today. Plus top claimants. |
| Giveaway page funnel | All visits. |

### Promotions reps tab

For each calendar month in the window, one row per creator with the number of
their published and closed shows dated in that month (Q20). A count of shows
whose creator isn't an owner is shown beside it. Clicking the name expands the
list of shows: date, show, venue, owners and a mismatch highlight. "Unknown
creator" holds shows with no `show_created` entry.

### Short links tab

Per slug: redirects, unique users, and blocked attempts (not staff, DJ
network), with a chart of redirects per day. Rolled-up data keeps unique users
per day, so unique users over windows older than 13 months are summed by day
(the tooltip says so).

### Site usage tab

- Signed-in users: distinct users per day, per week and per month, as a chart;
  a per-sub-site breakdown; and a per-user table (active days in the window,
  last seen).
- DJ studio network and station office network sessions: sessions per day,
  and an hour-of-week heatmap, as two series.

## Backend

### Where the code lives

Like KALX Staff Admin, the analytics backend acts on every sub-site, but it
reads other sub-sites' data. Following the `job_registry` pattern, **each
sub-site owns its metrics**, and registers them from `main.py`:

- `app/common/services/analytics_registry.py`: `register_metric_group(...)`.
  It holds metric groups (an ID, a tab, a function `(db, window) -> result`)
  that the analytics router calls.
- `app/common/services/tracking_service.py`: `record_event(...)`, which skips
  everything while the request is impersonating, plus normalization helpers.
- `app/common/routers/analytics.py` (`/api/analytics`): the metric endpoints,
  the window parsing, and the signed-in active-day beacon. Access is
  `get_site_or_promotions_admin` for metrics, and `get_staff_member` for the
  beacon.
- `app/pass_giveaway/analytics.py`: the pass giveaway's metric functions,
  including site usage for its guest networks.
- `app/short_links/analytics.py`: the short links metrics.
- `app/common/analytics.py`: the signed-in site usage metrics.

There's no `app/analytics/` backend package. The analytics sub-site is
frontend only, like admin.

### Model (`app/models/analytics_event.py`, one Alembic migration)

`analytics_event`:

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `occurred_at` | datetime (UTC), indexed | |
| `event_type` | str, indexed | see below |
| `area` | str | `common/areas.py` |
| `actor_email` | str, nullable | signed-in user; null for guests |
| `network` | str, nullable | `dj_studio`, `station_office` or null |
| `ref` | str(64), nullable, indexed | visit ID, guest session ID, spin ID or pass ID |
| `entity_type` / `entity_id` | str / int, nullable | e.g. `show`, `short_link` |
| `dj_name` | str, nullable | normalized DJ name |
| `dimension` | str, nullable | outcome or result, e.g. `given_away`, `blocked_not_staff` |
| `details` | JSON, nullable | small extras |

Composite index on `(event_type, occurred_at)`.

`analytics_daily_count` (rollups): `day` (date), `event_type`, `area`,
`entity_type`, `entity_id`, `actor_email`, `network`, `dj_name`, `dimension`,
`count`. Unique on all columns except `count`.

Metrics read from both tables: raw rows for the last 13 months, and rollups
for older days.

### Event types

| Event | Recorded by | Fields |
|---|---|---|
| `active_day` | `POST /api/analytics/beacon` (login required), once per user per sub-site per day (deduplicated on the server) | `actor_email`, `dimension` (sub-site) |
| `guest_session` | `POST /api/pass-giveaway/analytics/session` (both guest networks) on session start | `network`, `ref` (session ID) |
| `giveaway_visit` | `POST /api/pass-giveaway/analytics/giveaway-visits` on giveaway page load | `ref` (visit ID), `entity_id` (show), `dj_name`, `dimension` (outcome) |
| `spin_match_suggested` | `GET /api/dj/spin-matches`, the first time a (spin, show) match is returned (deduplicated on the server) | `ref` (spin ID), `entity_id` (show), `dimension` (`ignored`, `dismissed` or `clicked`) |
| `spin_match_giveaway` | `POST /passes/{id}/giveaway`, when the show had a popup in the last 2 hours | `entity_id` (show), `ref` (pass) |
| `short_link_redirect` | `/go/<slug>` | `entity_id` (link), `actor_email`, `dimension` (`redirected`, `blocked_not_staff`, `blocked_dj_network`) |

A giveaway page visit and a spin-match suggestion are each **one row that
is updated** rather than a chain of events, so the nightly rollup can count
them without knowing what they mean:

- A visit starts with `dimension = "neither"`. `POST /passes/{id}/giveaway` and
  `POST /shows/{id}/attempt` take an optional `visit_id` and raise it to
  `given_away` or `tried` (never lower). The DJ name comes from the outcome
  if there is one; otherwise `PUT …/giveaway-visits/{visit_id}/dj` keeps it in
  step with the name field (debounced). A blank name is "Unknown DJ".
- A suggestion starts as `ignored`. `POST /api/dj/spin-matches/{id}/dismiss`
  gains `action=dismissed|clicked` and sets it.

Only real DJ use is tracked (`pass_giveaway/services/tracking.dj_tracking`):
the DJ studio network, and in staging, signed-in Sublist DJ staff. Promotions
staff previewing the DJ view aren't.

The guest-reachable routes are in `pass_giveaway/routers/analytics.py`. They
use `GuestRedactingRoute`, are on the guest allowlist and in `SECURITY.md`,
validate their IDs (`[A-Za-z0-9_-]{8,64}`) and are rate-limited.

### Rollup job

`app/common/jobs.py` gains "Roll up analytics events", which runs nightly:

1. Roll everything older than 13 months into `analytics_daily_count`, by
   Pacific day. `ref` and `details` are dropped.
2. Delete the rolled-up raw rows.

### Window parsing

`?preset=last_30_days|last_month|this_quarter|last_quarter|this_year|last_year|all_time`
or `?from=YYYY-MM-DD&to=YYYY-MM-DD` (inclusive, Pacific). The response echoes
the resolved dates.

### Config and areas

- `common/areas.py`: add `ANALYTICS_AREA = "KALX Staff Analytics"` for the
  rollup job.
- Retention (13 months) is a constant in `tracking_service.py`, not config.

### Tests

- Each metric against seeded fixtures, including the edge cases: future shows
  excluded from utilization, low-sample flags, best-outcome-wins, "Unknown DJ",
  normalization of phones, names and DJ names, and the same-name flag using
  `win_frequency_days`.
- Window parsing for every preset, including quarter and year boundaries.
- Tracking: nothing is recorded while impersonating; the server-side dedupe for
  active days and spin matches; and the `/go/` results.
- The rollup job: counts are kept, and metrics give the same answer before and
  after rolling up.
- Access: Promotions admins and site admins can read metrics; other staff get
  403; guests get nothing (the allowlist test).

## Frontend

### Analytics sub-site (`frontend/src/analytics/`)

- `subsites.ts` and `App.tsx`: register the sub-site (path `/analytics/`,
  name, site admins and Promotions admins).
- `AnalyticsApp.tsx`: routes `/` (Overview), `/venues`, `/venues/:venueId`,
  `/djs`, `/djs/:djName`, `/reps`, `/short-links` and `/usage`.
- `AnalyticsLayout.tsx`: the header with tabs and the shared `WindowPicker`.
  The window is kept in the query string and carried over between tabs.
- `MetricCard`, `MetricTable`, `MetricChart` (Recharts, with a chart/table
  toggle) and `ExplanationPopover` (ⓘ).
- `api.ts`: `analyticsAPI`. `types.ts`: metric and explanation types.
- The home page gets an Analytics card.

### Tracking

- `common/`: a `useActiveDayBeacon()` hook, called by each sub-site's app
  shell. It sends at most one beacon per sub-site per day (remembered in
  `localStorage`, and deduplicated on the server as well).
- `pass-giveaway/tracking.ts`: guest session tracking for every pass
  giveaway page a guest opens (session ID in `sessionStorage`, renewed after
  30 minutes idle). The giveaway page creates or continues a visit ID (in
  `sessionStorage`, kept for 10 minutes), sends it with giveaway and "tried"
  calls, and sends DJ name changes (debounced).
- `SpinMatchNotifier.tsx`: sends `action` with dismiss and click-through.

### Staff Admin

`ShortLinksSection.tsx` gains a "Clicks (30 days)" column, linking to
`/analytics/short-links?slug=…`.

### Tests

Each tab renders with mocked API data; switching the window updates the URL
and refetches; explanation popovers show their text; the beacons fire once;
the giveaway page sends its visit ID. Follow the act() rules in CLAUDE.md.

## Docs and config

- CLAUDE.md: the sub-site in the map tables, the new folders, routes and
  tables, the registries, and the guest routes.
- `SECURITY.md`: the new guest tracking routes, and who can see analytics.
- `backend/tests/common/test_guest_access.py`: the allowlist entries.
- `frontend/package.json`: `recharts`.

## Rollout checklist

1. Deploy. Tracked metrics start collecting from this day, and their
   tooltips show "Tracked since".
2. Check in KALX Staff Admin that the rollup job is listed.
3. Check on staging that a DJ studio visit, a giveaway, a "tried" click, a
   spin-match popup and a `/go/` redirect each appear in analytics.
