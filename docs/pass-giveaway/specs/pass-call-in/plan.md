# Implementation Plan: Tracking Pass Call-Ins

## Overview

After a show closes, a promotions rep "calls in" the passes: they email the
guest list to the venue or promoter. Some reps want to keep track of which
closed shows they've already done that for. This feature adds a per-venue and
per-promoter setting, **Track when I've called in the passes** (off by
default). When it's on, closed shows get a **Mark Passes Called In** button
next to the guest list on the promotions show page.

Design agreed 2026-11-12.

## Decisions

| # | Question | Decision |
|---|---|---|
| 1 | Data model | Not a new status. The show stays `closed` (so every `status == "closed"` check is untouched) and gains nullable `passes_called_in_at` and `passes_called_in_by` columns. |
| 2 | Venue or promoter | `show.promoted_by` decides, like Hold Close Notifications: the show's promoter's setting if it has one, otherwise the venue's. |
| 3 | Child venues | Each venue has its own setting; nothing is inherited from a parent venue. |
| 4 | Show page controls | A "Mark Passes Called In" button in the "Guest List for Venue" header, with no confirmation. Once marked, a hint line reads "Passes called in <time> by <name>" with an Undo link, which clears both columns. |
| 5 | Re-opening | Clears both columns, like the close notification fields. |
| 6 | Guest list changes after call-in | No warning in this version. The rep can Undo, call in again and re-mark. |
| 7 | Shows list | Not shown. Few venues will use it, and a badge or filter would imply other venues' closed shows haven't been called in. |
| 8 | Turning the setting off | Marks are kept and hidden; turning it back on shows them again. |
| 9 | Who sees it | Promotions only. Staff and DJ views are unchanged. |
| 10 | Audit log | `passes_called_in` and `passes_call_in_undone` events, `area` = pass giveaway. |
| 11 | Past shows | No date limit on marking. |
| 12 | Setting | `track_pass_call_in` on `venues` and `promoters`, default false. Checkbox straight after "Wait for me to send close notifications" on both forms, labelled "Track when I've called in the passes", hint: "Closed shows get a Mark Passes Called In button next to the guest list, so you can keep track of which ones you've sent to the venue." |
| 13 | Header badge | None. The hint line in the guest list box is the only indicator. |
| 14 | Reminder | While unmarked, the guest list box says "Passes haven't been called in to the venue yet." |
| 15 | With held notifications | Independent; marking is allowed before notifications are sent. Button order: Notify, Mark, Copy. |
| 16 | Backend | `POST /api/shows/{id}/passes-called-in` marks and `DELETE` on the same path undoes. Both refuse (409) a show that isn't closed or whose `promoted_by` has the setting off. "By" is `promotions.name or promotions.email`. The show response gains `track_pass_call_in` (resolved from `promoted_by`), `passes_called_in_at` and `passes_called_in_by`. `passes_called_in_by` is redacted for guests like `close_notifications_sent_by`. |
