# Implementation Plan: Entering Winners on the Show Form

## Overview

Sometimes a promotions rep creates a show that replaces one that was cancelled,
postponed or moved to another venue, and some of the original show's on-air and
staff winners need to carry over. This feature adds a hidden section under
**Advanced** on the New Show and Edit Show screens where the rep types those
winners in by hand.

It is meant for rare use, and the UI discourages it.

Design agreed 2026-11-08.

## Decisions

| # | Question | Decision |
|---|---|---|
| 1 | Where winners come from | Typed in by hand. There is no picker for winners from a cancelled show. |
| 2 | Edit Show | Add only. The show's current winners and claims aren't edited here; Show Detail still changes and releases them. |
| 3 | Rules | Skip the venue's win-frequency limit (it's the same win, not a new one). Staff winners bypass the lottery. Still enforce the venue's email and +1 guest-name rules. Staff winners follow the normal claim rules: Active only (`auth.can_claim_staff_passes`, so not 🆕) and not on leave for the show (`ensure_not_on_leave_for_show`). |
| 4 | Not enough passes | Block the save and say how many passes are short. Never change the pass counts automatically. |
| 5 | Notifications | None. A notice tells the rep to contact the winners themselves. |
| 6 | Drafts | Allowed on drafts and published shows. |
| 7 | "Given away by" | An optional text field. A blank is stored as "Unknown", as in the legacy import. |
| 8 | Staff picker | `PersonAutocomplete`. The save rejects anyone who isn't eligible and gives the reason. |
| 9 | Duplicates | Block the same staff member twice, and anyone who already holds a pass to the show. On-air winners aren't checked for duplicates. |
| 10 | DJ-reserved pass pairs | Never filled. Pairs with `preassigned_dj` count as unavailable in the shortfall check. |
| 11 | Audit log | One entry per winner, `area=pass_giveaway`, actor = the rep, with new event types `on_air_winner_entered_by_promotions` and `staff_pass_assigned_by_promotions`. |
| 12 | The no-notification notice | Shown once the section is open, with no checkbox: "**No one is notified.** Winners you add here aren't emailed or texted. Contact each of them yourself to let them know about this show." |
| 13 | Staff already waiting on the show | Do what a normal claim does: give them the pass and remove their alternate-list place or pending lottery entry, with no email. |
| 14 | Closed shows | The section is hidden. Reopen the show first. |
| 16 | Hiding the fields | See "UI" below. |

## UI

Inside Advanced, the section starts as one collapsed link-style toggle,
styled like the "▶ Advanced" toggle, with a hint under it:

> ▶ Enter winners from a previous show
> *Only for a show that replaces one that was cancelled, postponed or moved. Most shows should leave this alone.*

Clicking it reveals:

1. The "No one is notified" notice.
2. **On-air winners**: an "Add on-air winner" button. Each row has name, phone,
   email (required if the venue requires email addresses) and "Given away by"
   (optional), plus a remove button.
3. **Staff winners**: an "Add staff winner" button. Each row has a
   `PersonAutocomplete`, a "+1 guest" checkbox and a guest name (required if
   the venue requires guest names), plus a remove button.
4. A live count of the passes the rows need against the passes available,
   with the shortfall if there is one.

No empty rows are shown until an Add button is clicked. The section never
opens by itself, even on Edit for a show that already has winners. The
show's existing winners still appear on Show Detail.

If the rep collapses the section with rows filled in, the rows are kept and
saved, and the toggle shows the count: "▶ Enter winners from a previous show
(3 entered)".

## Passes

- On-air winners fill available pass pairs that aren't reserved for a DJ.
- Staff winners fill available staff passes. A +1 guest uses a second staff
  pass (a guest hold, `guest_of_pass_id`).
- On Edit, the available passes are counted after any change to the pass
  counts in the same save.

## Backend

- `ShowCreate` and `ShowUpdate` gain optional `on_air_winners` and
  `staff_winners` lists.
- Everything is validated before anything is saved, so one bad row saves
  nothing (the show itself included).
- The checks and pass assignment are in
  `pass_giveaway/services/entered_winners_service.py`. The legacy import's
  `_assign_winners_and_claims` uses its `assign_winners_and_claims`.
- `GET /api/shows/staff-pass-claimants` (promotions only) lists Active staff
  for the staff picker. The form fetches it only when the section is opened.
- Closed and deleted shows reject the lists.
