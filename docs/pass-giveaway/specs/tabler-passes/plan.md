# Implementation Plan: Tabler Passes for Co-Announce Shows

## Overview

At a co-announce show, members of the Publicity department sit at the KALX
table, hand out swag and promote KALX. This feature sets aside some of a
co-announce show's staff passes as **tabler passes** for them. Only Publicity
members can claim one, and promotions can assign one to any current staff
member.

Tabler passes always come out of the show's staff passes. They never have a +1
guest, never have an alternate list and are never in the lottery.

Design agreed 2026-11-11.

## Decisions

| # | Question | Decision |
|---|---|---|
| 1 | Where tabler passes come from | Always out of the show's staff passes. To make room, promotions raises the Staff Pass Adjustment. |
| 2 | The default of 2 | Each show has its own count, which starts at 2 when Co-Announce is checked. The 2 is a constant in the code, with no settings page. |
| 3 | Limits on the count | 0 up to the number of staff passes still unclaimed. A count that would push out staff who have already claimed passes isn't saved. Instead, the error says how many staff passes are claimed. |
| 4 | Lowering the count, or turning Co-Announce off, after tabler passes are claimed | Allowed after a confirmation dialog that names who will lose their pass. Those claims are released and each person is emailed. |
| 5 | Unclaimed tabler passes | They stay until promotions lowers the count by hand. Nothing releases them automatically. |
| 6 | Tabler pass plus another pass for the same show | Not allowed. One pass per person per show: a tabler pass rules out a staff pass, a lottery entry and an alternate list spot for the same show, and the other way around. The page tells them to release the other one first. |
| 7 | Who can claim | Anyone with the Airtable department "Publicity" who is current staff (Active or 🆕, `auth.is_current_staff`). Tabling is a job, not a perk, so 🆕 students can do it. |
| 8 | How claiming works | Always first come, first served, never in the lottery, even on lottery shows. Claims use the same close cutoff as staff passes (`PassService._validate_show_claimable`). A tabler can release their own pass until the cutoff, and it goes back to being an open tabler pass. |
| 9 | Promotions show page | A tabler section that lists the claims. Promotions can release a claim or assign any current staff member (Active or 🆕, not only Publicity). |
| 10 | Guest list | "1 pass for Name (KALX Co-Announce Table)", with the same phone and email rules as staff passes. This applies to the venue email (`ShowService._build_guest_list_text`) and to the guest list on the promotions show page. |
| 11 | Notifying Publicity | No badge on the staff show list and no email when a show is published. The staff show page lists who else is tabling. |
| 12 | Who sees tabler passes | Everyone can see that there are tablers. Only Publicity members can claim one. |
| 13 | Lowering the staff passes (pass pairs or Staff Pass Adjustment) | Passes are removed in this order: unclaimed staff passes, unclaimed tabler passes (which lowers the tabler count), +1 guest passes, staff claims (bumped claimants go to the alternate list, as today), and tabler claims last (released with an email, no alternate list). The edit form warns whenever this will lower the tabler count. |
| 14 | Freed passes | Become staff passes again, and the alternate list fills them right away (`AlternateService.fill_open_passes`), with the usual emails. |
| 15 | What non-Publicity staff and DJs see | (a) On the staff show page, everyone sees a read-only "KALX Co-Announce Table" section with the claimed count and the tablers' names. (b) The DJ pages don't change. (c) The staff show list's count of staff passes left leaves out tabler passes. |
| 16 | Someone promotions assigns | They can release it themselves, the same as a Publicity tabler. Being on leave for the show (`ensure_not_on_leave_for_show`) blocks a tabler claim or assignment, just as it blocks a staff pass. |
| 17 | Emails | The tabler is emailed when (a) promotions assigns them, (b) promotions releases their pass, and (c) they lose it because the tabler count or the staff passes were lowered, or Co-Announce was turned off. No email when they act themselves, and none to promotions. |
| 18 | Closing, reopening, unpublishing and deleting | Tabler claims follow the same rules as staff claims. Unclaimed tabler passes are left off the guest list. |
| 19 | The tabler's own views of their passes | Tabler passes appear wherever the person's staff passes appear, labeled "🪑 KALX Co-Announce Table". That's My Passes: the directory profile doesn't list passes. |
| 20 | Audit log and analytics | Audit log entries for claims, releases, assignments and count changes, with `area=pass_giveaway`, because staff passes already get them (`pass_claimed`, `pass_released`). No analytics metric. |
| 21 | Where the count control appears | The New Show and Edit Show forms. Not legacy import, which is being removed soon. |
| 22 | How passes are stored | See "Data model" below. |

## Data model

- Add `shows.num_tabler_passes` (Integer, not null, default 0, server
  default 0), in a new Alembic migration.
- Store tabler passes as `Pass` rows with `pass_type = "tabler"`. They use
  `staff_id` and `claimed_at` like staff passes, and `has_guest`,
  `guest_of_pass_id` and the other guest columns always keep their defaults.
- Keep this invariant: staff rows plus tabler rows = `show.num_staff_passes`
  (pass pairs plus Staff Pass Adjustment), and tabler rows =
  `num_tabler_passes`. When Co-Announce is off, `num_tabler_passes` is 0.
- Every existing staff pass query (lottery, alternate list, +1 guest passes,
  cut claims) filters on `pass_type == "staff"`, so tabler passes stay out of
  them without extra code. The checks that need both types are the
  one-pass-per-person-per-show rule (decision 6), the guest list (decision 10),
  the staff member's own claimed passes (decision 19), and delete, close and
  reopen handling (decision 18). Each must be updated to include `"tabler"`.

## Backend

### Show create and update

- `ShowCreate` and `ShowUpdate` gain `num_tabler_passes` (int ≥ 0). On create
  with `co_announce=True` and no value, use 2. With `co_announce=False`, the
  value must be 0 or omitted.
- Changing the count, or turning Co-Announce off, converts rows between staff
  and tabler:
  - **Raising** the count turns unclaimed staff passes into tabler passes. If
    there aren't enough unclaimed staff passes (counting +1 guest passes as
    claimed), reject with a 400 that says how many staff passes are claimed
    (decision 3).
  - **Lowering** the count turns unclaimed tabler passes back into staff
    passes first. If that isn't enough, the request must carry a confirmation
    flag (for example `confirm_release_tablers: true`). Without it, return a
    409 that lists the tablers who would lose their pass, which the form shows
    in its confirmation dialog (decision 4). With it, release the newest
    tabler claims, turn those rows into staff passes and email each tabler
    (decision 17c).
  - Then run `AlternateService.fill_open_passes` for the show (decision 14).
- Lowering the staff passes (the pass pair or Staff Pass Adjustment update in
  `pass_service.py`, around the `staff_delta` logic) removes passes in the
  decision 13 order. Unclaimed tabler passes are removed after unclaimed staff
  passes, and `num_tabler_passes` goes down with them. Claimed tabler passes
  are removed last: release them and email each tabler, with no alternate
  list. A save that would do this also needs `confirm_release_tablers`, so the
  form asks first, as in decision 4.
- `tabler_service.plan` works out, before anything is saved, what the pass
  total change and the tabler count change would do together, so the 400 and
  the 409 come before any change is committed. When a save doesn't send
  `num_tabler_passes` for a show that was already co-announce, the count is
  whatever the total change leaves.

### Claiming and releasing

New endpoints, on the passes router (with `route_class=GuestRedactingRoute`,
like the rest of the pass giveaway):

- **Claim a tabler pass** (staff), `POST /api/shows/{id}/tabler-passes/claim`:
  requires a login, current staff (Active or
  🆕) and the Publicity department. Checks the close cutoff, leave, and
  one-pass-per-person-per-show (no staff pass, lottery entry or waiting
  alternate spot for the show). Takes any available tabler pass. Audit log
  `pass_claimed` (with the pass type in its details), no email.
- **Release my tabler pass** (staff, the holder), the existing
  `DELETE /api/passes/{id}/claim`: while the show is open. The
  pass becomes an available tabler pass again. Audit log `pass_released`, no
  email.
- **Assign a tabler pass** (promotions), `POST /api/shows/{id}/tabler-passes/assign`
  with `{"staff_id": …}`: any current staff member, with the
  same leave and one-pass rules, but no Publicity requirement. Audit log entry
  with the promotions rep as the actor, and an email to the tabler (decision
  17a).
- **Release a tabler pass** (promotions), the same `DELETE` endpoint: audit
  log, and an email to the tabler (decision 17b). The picker lists current
  staff from `GET /api/shows/staff-pass-claimants?include_new=true`.

`auth.can_claim_tabler_passes(staff)` checks current staff in the "Publicity"
department (`PUBLICITY_DEPARTMENT`). `/api/users/me` returns it as
`can_claim_tabler_passes`, which the staff show page uses.

The staff pass claim, the lottery entry and the alternate list join must also
reject someone who already holds a tabler pass for the show (decision 6).

### Show responses

- Promotions and staff show responses include `num_tabler_passes` and the
  tabler claims (pass id, staff id and name). Staff passes left, as counted
  for the staff show list and show page, leave out tabler passes.
- The staff show response includes whether the viewer can claim a tabler pass
  and whether they hold one.
- DJ responses don't change.
- Guests: tabler passes are in a show's `passes` the same way staff passes
  are, so guests on the trusted networks see tabler names but not their
  contact details (`GuestRedactingRoute` removes `staff_phone` and
  `staff_email`), the same as for staff passes. The new endpoints require a
  login.

### Guest list, close, reopen and delete

- `_build_guest_list_text` lists claimed tabler passes as
  "1 pass for Name (KALX Co-Announce Table)", with staff phone and email rules.
- Delete, close, reopen and unpublish treat claimed tabler passes like claimed
  staff passes (decision 18), including the cancellation notice to claimants.

## Frontend

### Show form (`promotions/` new and edit show)

- Under the Co-Announce checkbox, while it's checked, add a number input
  labeled "Tabler passes (for Publicity at the KALX Co-Announce Table)". It
  starts at 2. Help text: "Comes out of the N staff passes; M left for staff."
- Inline validation for the decision 3 limit, and the server's error if the
  inline check is out of date.
- When a save would release tabler claims (unchecking Co-Announce, lowering
  the count, or lowering pass pairs or Staff Pass Adjustment), show a
  confirmation dialog naming the tablers, then resend with the confirmation
  flag.
- When lowering pass pairs or Staff Pass Adjustment would lower the tabler
  count, say so on the form (decision 13).

### Promotions show page (`promotions/ShowDetail.tsx`)

- A "KALX Co-Announce Table" section on co-announce shows: "N of M tabler
  passes claimed", each tabler with a Release button, and a
  `PersonAutocomplete` to assign current staff.
- The guest list shows tablers as "1 pass for Name (KALX Co-Announce Table)".

### Staff show page (`staff/` show detail)

- A "KALX Co-Announce Table" section on co-announce shows with tabler passes,
  for every viewer: "N of M tabler passes claimed" and the tablers' names.
- Publicity members who can claim see a "Claim a tabler pass" button. If they
  hold another pass, lottery entry or alternate spot for the show, the button
  is replaced by a note telling them to release that first.
- The holder sees "Release my tabler pass" until the close cutoff.
- The regular staff pass section counts only staff passes.

### Staff show list and the person's own passes

- The staff show list's count of staff passes left leaves out tabler passes.
  There's no tabler badge.
- Tabler passes appear in the person's claimed passes and on their directory
  profile, labeled "🪑 KALX Co-Announce Table".

## Tests

- Backend: count limits and conversions; the 409 confirmation and the release
  emails; the decision 13 removal order; alternate fill after passes are
  freed; claiming (Publicity, 🆕 allowed, non-Publicity rejected, leave,
  cutoff, one pass per show both ways); promotions assign and release, with
  emails; the guest list text; close, reopen and delete; responses leaving
  tabler passes out of staff counts; the guest-access allowlist still passing.
- Frontend: the form's count input, help text and confirmation; the staff
  page's section for Publicity, non-Publicity and the holder; the promotions
  section. Follow the act() rules in `CLAUDE.md`.

## Out of scope

- Legacy import.
- Releasing unclaimed tabler passes automatically.
- Analytics metrics.
- Notifying Publicity of new shows.
- Showing tabler passes on DJ pages.
