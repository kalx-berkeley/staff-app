# Implementation Plan: Specialty Music Shows, Talk & Information Shows, and On-Air Identity From Spinitron

## Overview

Three related changes:

1. **Rename.** "Specialty Shows" become **Specialty Music Shows** everywhere
   people see them.
2. **Talk & Information shows.** A new kind of show, managed like specialty
   music shows, whose members are staff members rather than DJ personas.
3. **On-air identity from the schedule.** The `/pass-giveaway/dj` pages stop
   asking for a typed DJ name. Who is on air comes from Spinitron, and every
   DJ name stored as text becomes a Spinitron persona (or a show).

At any moment the **on-air identity** is one of:

| On air | Identity | Passes can be pre-assigned to |
|---|---|---|
| A DJ doing a regular music shift | The DJ's persona | The persona |
| A DJ hosting a Specialty Music Show | The show | The show, or the DJ's persona |
| Anyone (placeholder persona such as "News Team", or a DJ persona) hosting a Talk & Information show | The show | The show only |

Design agreed 2026-11-14. It ships in phases (see "Phases" below), so the old
DJ names can be cleaned up on real data before phase 3. Each phase is its own
branch and PR; phase 3's PR isn't merged until the clean-up is finished, since
any release cut after the merge includes it.

## Decisions

### Rename

| # | Question | Decision |
|---|---|---|
| 1 | Scope | Every user-visible "Specialty Show" becomes "Specialty Music Show": pages, emails, audit log text, KALX Staff Analytics labels and docs. URLs, API paths, tables, columns, file and code names stay as they are. |

### Talk & Information shows

| # | Question | Decision |
|---|---|---|
| 2 | Data model | One table. `specialty_shows` gains `category` (`music` \| `talk`). Owners, retiring, deleting, the Spinitron show ID mapping, pre-assigned passes and lottery entries are shared by both kinds. |
| 3 | Members | Music show members stay in `specialty_show_djs` (model `SpecialtyShowDJ`), now holding a persona (decision 9). Talk show members go in a new `talk_show_staff` table (model `TalkShowStaff`): `specialty_show_id` (FK to `specialty_shows.id`) and `staff_id`. The API refuses DJ members on a talk show and staff members on a music show. |
| 4 | Talk show members' rights | The same as music show DJ members: they can reserve passes for the show and enter the DJ lottery on its behalf from `/staff`. They must be current staff (Active or 🆕, `auth.is_current_staff`); being a Sublist DJ is not required. As with music shows, owners can reserve only if they're also members. |
| 5 | Telling the schedule a talk show is on | By Spinitron show ID only (`specialty_show_spinitron_shows`), never by title. A Spinitron show ID belongs to one show of either kind. A show that changes kind gets a separate Spinitron show. |
| 6 | Navigation | Two nav items on `/pass-giveaway/staff`: "Specialty Music Shows" (`/staff/specialty-shows`, unchanged) and "Talk & Info Shows" (`/staff/talk-shows`, new). Both use the same list and detail components, with a category prop. |
| 7 | Notifications and Profile Settings | Talk shows get exactly the same treatment as music shows (emails, the "my shows" section of Profile Settings, notification settings), labelled by kind. Emails to music show members go persona → staff instead of matching DJ name text. |
| 8 | Sublist DJ eligibility | Talk show playlists are left out of the directory's qualifying-shift check, like specialty music shows. The `specialty_show_ids` provider returns both categories, so the directory code doesn't change. |

### Personas instead of DJ name text

| # | Question | Decision |
|---|---|---|
| 9 | Music show DJs | Stored as `persona_id` plus a cached persona name for display. |
| 10 | Pass and record storage | Every DJ name text column gets persona and show identity columns alongside it: pre-assignments (a persona *or* a show, so `preassigned_dj` stops holding show names), giveaways (decision 11), `show_attempts`, `lottery_entries`, `analytics_event` and `analytics_daily_count`. Phase 2b adds only the columns a picker fills (pre-assignments, lottery entries, music show DJs). The rest (giveaways, attempts, analytics) arrive in phase 3, filled by its migration, since until then the only source is the typed DJ name. |
| 11 | Giveaway credit during a specialty music show | Both. Giveaways store `given_away_persona_id`, `given_away_specialty_show_id` and a text snapshot of the identity's label. On `passes` and `on_air_winners`. |
| 12 | Promotions pre-assigning | One picker offering personas linked to current staff (`staff.dj_personas`), plus music and talk shows, each labelled by kind. "Suggest by date" and "suggest by genre" return identities instead of names. |
| 13 | Pre-assigning a persona on a day they aren't the identity | Warn but allow. The warning says what the schedule shows for that date, for example "X isn't scheduled that day" or "X hosts *Talk Show Y* that day, so assign it to the show". |
| 14 | Self-service on `/staff` (reserving and the DJ lottery) | Pick from your own personas, defaulting to the one scheduled on the pass's date if any. The same picker includes the music and talk shows you're a member of. |
| 15 | Music show DJ editor | Offers only personas linked to staff. |
| 16 | Inactive personas | In all three pickers (decisions 12, 14 and 15), a staff member's personas with no playlist in the last 6 months are hidden. This applies only when the person has several personas *and* at least one of them has had a playlist in the last 6 months. If none has, all of them are offered. Personas already assigned are always shown. |
| 17 | Last playlist dates | Each entry in `staff.dj_personas` gains `last_playlist_at`, filled by a nightly job in common code (one Spinitron call per persona, `/playlists?persona_id=X&count=1`). The pass giveaway and the directory both read it without importing each other. |

### On-air identity on the DJ pages

| # | Question | Decision |
|---|---|---|
| 18 | The DJ Name box | Removed from every `/pass-giveaway/dj` page, together with the localStorage name, the DJ name autocomplete and the mismatch warning. The `X-DJ-Name` log header carries the identity label instead. |
| 19 | Showing the identity | The giveaway page (`/dj/shows/:id/giveaway`) and "Your pre-assigned shows" on `/dj/shows` show the identity prominently, with "If this isn't you, create your Spinitron playlist". During a specialty music show, "Your pre-assigned shows" lists both the show's passes and the DJ persona's passes for that date. During a talk show it lists only the show's. |
| 20 | Co-hosts | Only the playlist's persona counts. Other personas listed on the Spinitron show are ignored. |
| 21 | No identity (automation, FREEFORM, a placeholder persona with no talk show mapping, a gap, Spinitron down with nothing cached) | The page warns but still allows the giveaway, which is recorded as unattributed. Pre-assigned passes don't appear. |
| 22 | Subs and stale schedules | No manual override. A sub becomes the identity once their own playlist has a logged track (decision 24). |
| 23 | Keeping the schedule fresh | The full schedule sync still runs every 6 hours. Also, the schedule is re-synced from Spinitron 10 minutes before each slot starts, to catch last-minute changes. Through the changeover, while a DJ page is open, the server polls Spinitron **spins** every 60 seconds (`SpinitronService.fetch_spins`), not the whole schedule. A spin naming a playlist the app hasn't seen triggers one `/playlists/{id}` fetch for its persona and show. Polling stops at the first spin in a playlist from the new slot, or 15 minutes after the changeover. |
| 24 | Which playlist is on air when several overlap | 1. Among playlists overlapping now, the one with the most recent spin wins. 2. Otherwise, the scheduled show from the latest sync. Consequences: a DJ running over keeps the identity until the next DJ logs a track; a DJ who starts their own playlist early and logs a track takes over automatically; a sub shows as the scheduled DJ until their first track. Duplicate playlists are resolved by whichever is getting tracks. |
| 25 | Switching over early | In the last 10 minutes of a slot, a prompt offers "I'm <next identity> (N pre-assigned passes) — switch now". It lasts until the changeover and has a "Switch back to <current>" link. It's stored in the browser (the DJ studio has one computer). The full pass list appears only after switching. There's no prompt when the next slot has no identity. |
| 26 | Who decides the credit | The server, from the schedule. The page can send only "early switch to slot S", which the server accepts only if S is the next slot and starts within 10 minutes. |
| 27 | `/dj/my-passes` | Shows the on-air identity's giveaways (or the next identity's after an early switch). Personal history across all of a person's personas and shows is on the signed-in `/staff` My Passes page, which must cover every persona and show they belong to. |
| 28 | Fixing credit | Promotions only, in the pass giveaway's Promotions → Admin page: an "Unattributed giveaways" list, and a re-credit action for any giveaway using the decision 12 picker. Each re-credit is an audit log entry (`area` = pass giveaway). |
| 29 | Analytics | New events are keyed by identity (persona or show), so a talk show gets its own row on the DJs tab. Giveaway-visit tracking uses the identity instead of the typed name. |

### Clean-up and migration

| # | Question | Decision |
|---|---|---|
| 30 | Finding names that don't match | A one-time script in `backend/scripts/` reports, for every DJ name text value in every table (open, historical and analytics records alike), the persona it matches (exact, case-insensitive; any Spinitron persona, not only staff ones) or that it matches none. Misses are fixed by hand on real data before phase 3, by mapping the name (in `dj_name_mappings`) to a persona, a show, or no one (left unattributed, for placeholders like "Unknown"). Names a show and a persona share, or several personas share (unless exactly one is a staff member's), count as misses. Built as `scripts/spinitron_identity_report.py`, with the matching in `app/pass_giveaway/services/dj_name_matching.py`; it exits 1 while anything needs fixing. |
| 31 | Migration | Fills the persona and show columns for every record, historical and analytics included, using `dj_name_matching` and the mappings. It refuses to run while *any* record is still unmatched. |
| 32 | Old text columns | Dropped in a later change, once phase 3 has settled. |

## Phases

1. **Rename and Talk & Info shows.** Decisions 1–8. (Shipped.)
2. **2a: The clean-up script.** Decision 30. Released on its own so the
   clean-up can start straight away.
3. **2b: Personas where someone picks them.** Decisions 9–17, with the
   persona columns on pre-assignments, lottery entries and music show DJs.
   New writes fill both the persona columns and the old text columns.
4. **3: DJ pages use the schedule.** Decisions 18–29 and the migration
   (decision 31), which also adds the giveaway, attempt and analytics
   columns. Re-run the script on release day; release only at zero misses.

Later: drop the text columns (decision 32).

## Facts this plan relies on

- The cached `spinitron_playlists` and `spinitron_shows` tables store only
  the first persona and a resolved DJ name. They need `show_id` (and the
  playlist's own persona) for decision 5.
- `/api/dj/on-air` prefers a playlist over a show covering the same moment.
- A Spinitron playlist has one `persona_id`. A show can list several personas.
- Placeholder personas are configured in `SPINITRON_PLACEHOLDER_PERSONA_IDS`.
- Self pre-assignment (`POST /passes/{id}/preassign/self`) and the DJ lottery
  already take the DJ name from the staff profile, checking specialty show
  membership by matching text in `specialty_show_djs`.
- The lottery stores a specialty show's name in `passes.preassigned_dj`
  (`lottery_service.py`).
- The directory's `dj_shift_playlists` covers only the previous and current
  quarter, so it can't answer the 6-month question in decision 16.
