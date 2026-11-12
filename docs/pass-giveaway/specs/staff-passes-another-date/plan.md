# Implementation Plan: Staff Passes on Another Date

## Overview

A few venues give KALX the on-air pass pairs for one night's show and the
staff passes for a different night (for example pairs for Friday, staff passes
for Saturday). This feature handles that by creating **two ordinary shows**:
an on-air show with the pass pairs and no staff passes, and a staff show with
the staff passes and no pass pairs. Each show has one real date, so leave
checks, lotteries, auto-close, alternates, guest lists and calendars all work
unchanged.

Design agreed 2026-11-12.

## Decisions

| # | Question | Decision |
|---|---|---|
| 1 | Data model | No link between the two shows. Each is a normal show and is edited, closed and deleted on its own. |
| 2 | Zero-pair shows | `num_pass_pairs` may be 0 (0–5) when the show has at least one staff pass. A show still needs at least one pass of either kind. |
| 3 | Venue setting | `venues.staff_pass_day_offset`, nullable integer, −30 to 30, never 0 (0 is saved as blank). Blank for almost every venue. |
| 4 | Venue form | A "Rarely used" collapsed section at the end of the defaults, open only when the setting is filled in, saying most venues should leave it blank. |
| 5 | Show form | Only new single-day shows at a venue with an offset are split. The rep enters the on-air show's date and time as usual. A box says saving creates two shows, lists both with their dates, passes and close times, and lets the rep change the staff show's date, time and close date/time. These follow the on-air show's values (date + offset, same time, close shifted by the same number of days) until the rep edits them. The save buttons say "Save 2 Drafts" and "Publish 2 Shows". |
| 6 | Multi-day shows | Not split. The box says a multi-day show is created as one show with both kinds of passes. |
| 7 | What goes where | On-air show: the pairs, staff adjustment = −pairs, no tabler passes, on-air winners, no staff winners. Staff show: 0 pairs, adjustment = the staff pass total, the tabler passes, staff winners, no on-air winners, no DJ reservation prohibition. Everything else (name, bands, descriptions, instructions, co-announce, lottery, auto-close) is copied to both. |
| 8 | Backend | `POST /api/shows/split` takes the show as entered plus `staff_show_date`, `staff_show_time`, `staff_planned_close_date` and `staff_planned_close_time`. It validates both shows and both sets of entered winners before creating either, and returns `{on_air_show, staff_show}`. Publishing calls the publish endpoint for each. |
| 9 | Views | The DJ view hides shows with no pass pairs. The staff view hides shows with no staff passes, including existing shows adjusted to 0 staff passes. |
| 10 | Editing a show with no staff passes | Changing its pair count keeps it at 0 staff passes until the rep changes the Staff Pass Adjustment. |
| 11 | Audit log | Each show gets its usual `show_created` event. The staff show's carries the on-air show's ID as `split_from_show_id`. |
