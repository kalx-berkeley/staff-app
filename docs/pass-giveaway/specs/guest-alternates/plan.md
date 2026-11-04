# Implementation Plan: Waiting Guests on the Alternate List

## Overview

Today a staff member claiming a pass with a +1 guest chooses what happens if the
guest can't attend: attend alone, or release both passes. A bumped guest
disappears for good.

This feature adds two options that put the guest on the alternate list instead.
The guest waits behind staff alternates and gets any pass that frees up before
the show closes. It applies to direct claims, the lottery and the alternate
queue.

Scope: staff passes only. DJ pass pairs are unchanged.

This changes two decisions in `../staff-pass-alternates/plan.md`: its Q2
(previously bumped guests are never restored) and Q13 (an alternate's guest
request is dropped when no pass is left). Both now apply only to option 1.

## The four options

The form question stays "If my guest can't attend". The answer is stored as
`guest_fallback`, which replaces the `only_attend_with_guest` boolean.

| Option | Value | If the guest has no pass | If the guest is still waiting at close |
|---|---|---|---|
| 1 (default). I'll still attend without them | `attend_alone` | Guest is dropped | N/A |
| 2. Release my pass too (cancel both) | `release` | Both lose their passes right away | N/A |
| 3. Put them on the alternate list, and I'll attend either way | `wait` | Guest waits | Staff member attends alone |
| 4. Put them on the alternate list, but release my pass if they don't have one when the show closes | `wait_then_release` | Guest waits | Staff member is released, and neither attends |

If the guest has a pass at close, both attend under every option.

### Pros and cons (always shown under every option)

| Option | Pro | Con |
|---|---|---|
| 1 | You keep your pass. | If your guest loses their pass, they won't automatically get another chance. |
| 2 | If your guest loses their pass, you find out right away and can make other plans. | You lose your pass at that moment, even if another pass frees up later. |
| 3 | You keep your pass, and your guest can still get one until the show closes. | You may not know if your guest can come until the show closes, and staff get freed passes first. |
| 4 | You only go if you can go together, and your guest can still get a pass until the show closes. | You may not find out until the show closes, and you could lose your pass at that point, with no time to make other plans. |
| 2, alternate form ("Skip me until there's a pass for both of us") | You only get a pass if there's one for your guest too. | You're skipped until two passes are free at once, so you may never get one. |

## Agreed decisions (from grilling session, 2026-11-04)

| # | Decision |
|---|---|
| Q1 | A staff member chooses at claim time whether they still attend if their guest is still waiting at close. That creates options 3 and 4. |
| Q2 | All four options appear on the direct claim, lottery and alternate forms. |
| Q3 | A guest can start on the list when no pass is spare, only under options 3 and 4 (see Q13). |
| Q4 | Waiting guests are ordered by `guest_priority_at`: the host's claim time for a guest included in the claim. |
| Q5 | A freed pass with no staff waiting goes to the next waiting guest automatically, as a normal guest hold. A later staff claim can still bump that guest, who returns to the same place. |
| Q6 | A single free pass goes to a waiting guest ahead of an alternate who needs a pair. When two are free, the pair goes first. Pair alternates can't bump guest holds. |
| Q7 | "Remove my guest" works for seated and waiting guests, for the staff member and promotions staff. The staff member keeps their pass. |
| Q8 | A waiting guest is stored on the host's pass row, not in `staff_pass_alternates`. `guest_fallback` replaces the boolean on all three tables. |
| Q9 | The option 4 release happens at close, while the show is still published. Forms show the pros and cons. |
| Q10 | Option 4 hosts are released one at a time, last in guest order first, reassigning the pass after each. A release can seat an earlier guest and save that host. |
| Q11 | At close, an alternate with option 4 only gets a pass if two are free. Before close, they can take one while their guest waits. |
| Q12 | A staff member released at close is recorded as an alternate entry expired by that close, using their original claim time. They appear under the guest list, share the held email flow, and return to the list if the show reopens. |
| Q13 | The wording is as above, with option 1 as the default. All four options show whenever a spare pass exists. |
| Q14 | "Add a guest" is available after claiming, and a guest added later ranks by when they were added. A name fix keeps their place. Changing the option means removing and re-adding, which goes to the back of the line. |
| Q15 | There are six new or changed host emails (below). When a show closes, each person gets a single email, not several. |
| Q16 | Waiting guests appear in a separate, separately numbered section below the staff alternates. |
| Q17 | Pass count changes, leave, reopen, delete and unpublish follow the edge case table below. |
| Q18 | With no spare pass on a direct claim, the form shows only options 3 and 4, with the note "There's no pass free for your guest right now, so they'd start on the alternate list." If the last spare goes while the form is open under option 1 or 2, the claim fails with an explanation. |
| Q19 | Pros and cons use the text above and are shown under every option at all times. |
| Q20a | A lottery drawn by a close and the close outcome are one email. |
| Q20b | On a show holding its close emails, "you got a pass" and lottery results go out right away, and everything else waits for the rep. Those people get two emails. |
| Q20c | A rep's guest list email stays separate from their personal outcome email. |
| Q21 | Remaining rules are listed under "Other rules" below. |
| Q22 | Delivered in three stages on the `guest-alternates` branch, not merged to `main` until stage 3 is done. |

## Rules

### Who gets a free pass

`fill_open_passes` assigns passes in this order:

1. Staff alternates who can take one pass, in queue order. A seat is a free pass
   or, failing that, the last guest hold in guest order.
2. Alternates who need a pair, if two passes are free. They never bump a hold.
3. Guests in `guest_priority_at` order: waiting guests and the guests of
   alternates just promoted.

A staff member who joins the list later still goes ahead of a guest already
waiting. Option 1 guests of promoted alternates can take a leftover pass, as they
do today, and otherwise are dropped.

### Guest order

`guest_priority_at` decides both who gets a pass first and who is bumped last, so
a guest bumped twice keeps their place.

| How the guest arrived | `guest_priority_at` |
|---|---|
| Included in a direct claim | Claim time |
| Lottery winner's guest | The entry's `entered_at` (the claim time lottery winners already get) |
| Promoted alternate's guest | Promotion time (the claim time) |
| Added after claiming | Time added |

Re-seating a guest must not reset this value.

### At close

Before the show is marked closed, in `ShowService.close_show`, so manual and
automatic closes both run it, and after any lottery draw that close triggers:

1. Find option 4 hosts whose guests are still waiting.
2. Release the one last in guest order.
3. Reassign that pass through `fill_open_passes`, skipping option 4 alternates
   unless two passes are free.
4. Repeat until nobody is left to release, then mark the show closed.

A host is released even if nobody else can use the pass. Option 3 hosts stay on
the guest list without their guest, and the guest stays attached to the pass in
case the show reopens.

### Emails

1. **Guest moved to the list:** their position and what happens at close under the
   chosen option.
2. **Guest got a pass:** not confirmed until close, and could still be bumped.
3. **Guest started on the list:** a change to the lottery and promotion emails, and
   to the on-screen message after a direct claim, which sends no email.
4. **Guest still waiting at close, option 3:** "You're on the guest list; your
   guest isn't."
5. **Released at close, option 4:** neither is on the guest list.
6. **Guest removed by promotions staff:** says who removed them.

**One email at close.** Each person gets one email built from the final result.
Bump and "guest got a pass" notices from the close step, and the results of a
lottery drawn by the close, fold into it.

On a show holding its close emails, "you got a pass" and lottery results go out
right away, and emails 4 and 5 wait with the other close emails. A show with only
waiting guests counts as having close emails to hold. Reps' guest list emails stay
separate.

### Display

- **Alternate list:** a "Guests waiting for a pass" section below the staff
  alternates, such as "Guest #1: Sam (guest of Alex)". All staff can see it, even
  when the staff list isn't open for joining.
- **Promotions staff:** a Remove button, and guests still waiting at close shown
  below the guest list.
- **My Passes:** the host sees their guest's position.
- **Release warning:** names the guest if they're next: "Your pass would go to Sam
  (Alex's guest)."

### Edge cases

These apply to guests under options 3 and 4.

| Situation | What happens |
|---|---|
| Fewer passes, guest's pass removed | Guest goes back to waiting |
| Fewer passes, host's pass removed | Host moves to the alternate list and the guest's request goes with them |
| More passes added | Normal order: staff first, then guests |
| Host on leave for the show | Guest is skipped but keeps their place |
| Show reopened | Waiting guests stay in line and can get any free pass |
| Show deleted | Waiting guests are cancelled, and the host's email mentions them |
| Show unpublished | Guests keep their place, and no passes are assigned until it's republished |

### Other rules

- Releasing a pass cancels the guest, whether seated or waiting.
- Removing a waiting guest means an option 4 host is no longer at risk of release.
- After close, guests can't be added or removed, and passes can't be released,
  until the show is reopened.
- A guest name required by the venue is needed when the guest joins the list.
- Existing claims convert to option 1 or 2 from their current setting.
- Guests bumped before launch stay dropped.
- Guests moving to the list, getting a pass and being removed are audit logged, as
  are releases at close.

## Data model

### `passes`

| Column | Notes |
|---|---|
| `guest_fallback` | Replaces `only_attend_with_guest` |
| `guest_waiting` | True while the guest is on the list. Implies `has_guest` is false and no hold is linked. |
| `guest_priority_at` | See "Guest order" |

`has_guest` stays true only while the guest has a seat, because the guest list,
guest confirmations and cancellation emails depend on it. `guest_name` is kept
while the guest waits. `_assign_claim` and `_clear_claim` reset all of these, which
is what makes a release cancel a waiting guest.

### `lottery_entries` and `staff_pass_alternates`

`guest_fallback` replaces `only_attend_with_guest`.

`staff_pass_alternates.source` gains `released_at_close`.

### Migration

Add the column, set it to `release` where `only_attend_with_guest` is true and
`attend_alone` otherwise, then drop the boolean. Use one Alembic revision, with
batch mode if SQLite needs it, and write a downgrade that maps both wait options
back to the boolean's false value.

## Implementation stages

Each stage gets its own review. Changes are staged for the user to commit.

### Stage 1: Data change, no change in behavior

- Add the migration and the model changes, with an enum or constants for the four
  values.
- Replace `only_attend_with_guest` across `pass_service.py`, `alternate_service.py`,
  `lottery_service.py`, the schemas, `routers/shows.py`, `routers/passes.py`,
  `routers/lottery.py`, `routers/alternates.py`, and the frontend `types.ts`,
  `api.ts`, forms and test fixtures.
- Forms still offer only options 1 and 2.
- All existing backend and frontend tests pass, with field names updated.

### Stage 2: Waiting guests

Option 4 behaves like option 3 at this stage. The release at close arrives in
stage 3, and the branch isn't merged before then.

**Backend**

- `PassService._displace_guest_hold`: keep the guest waiting under `wait` and
  `wait_then_release`, and retain the name.
- `PassService.claim_staff_pass`: allow a guest to start waiting when no spare
  exists. Today the request is rejected with a 400, or `has_guest` is silently
  ignored when the claim lands on a hold.
- `AlternateService.fill_open_passes`: remove the early return when no staff are
  waiting, seat guests in step 3, and skip guests whose host is on leave.
- `PassService._assign_guest_hold`: set a hold's `claimed_at` to the guest's
  `guest_priority_at`, so `_guest_holds_newest_first`, `display_order` and pass cuts
  all follow the guest order.
- `AlternateService.next_candidate` and the alternates `GET` response: name the
  waiting guest in the release warning, and add the guests section.
- `AlternateService.restore_on_reopen`: stop returning early when nothing is
  restored, so waiting guests can still get free passes.
- `AlternateService.enqueue_cut_claim`: carry a waiting guest's request with the
  host.
- `PassService.adjust_passes_for_show`: send removed holds back to waiting.
- `LotteryService._run_staff_lottery`: winners' guests wait under options 3 and 4.
- New endpoints to remove a guest, add a guest and correct a guest's name. They
  require a login, and promotions staff can remove any guest. Pass giveaway routers
  already use `GuestRedactingRoute`. Extend the guest access tests.
- `_notify_claimers_of_cancellation`: mention a waiting guest.
- Emails 1, 2, 3 and 6, plus audit events.
- Confirm that `_build_guest_list_text` and the frontend guest list leave out
  waiting guests, which depends on `has_guest` staying false.

**Frontend**

- A shared fallback options component with pros and cons, used by the direct claim
  form, the lottery form and `AlternateGuestForm`.
- Show the `+1` button when one pass is available, with only options 3 and 4
  offered.
- The guests section in `AlternateQueue.tsx`, the promotions views, My Passes and
  the release warning.
- Remove, add and name-fix actions on the claimed pass card.

### Stage 3: Close changes

- A new close step in `ShowService.close_show`, after the lottery draw and before
  the status change.
- `fill_open_passes`: a close mode that treats option 4 alternates as needing a
  pair.
- Released hosts become `staff_pass_alternates` rows with
  `source="released_at_close"`, `status="expired"` and `priority_at` set to their
  claim time. They need the same `resolved_at` as the entries `expire_on_close`
  expires, or `entries_expired_at_close` leaves them out, so pass one timestamp
  through.
- Check `restore_on_reopen` and `entries_expired_at_close` with these rows.
- Collect emails during the close and send one per person from the final result.
  This covers `_notify_guest_bumped`, promotion emails, `_notify_staff_guests_confirmed`,
  `AlternateService._email_no_pass` and, when a close triggers the draw, the
  `run_lottery` result emails. Called on its own, `run_lottery` keeps emailing as it
  does now.
- `run_close_side_effects` and `send_close_notifications`: hold and send emails 4
  and 5. Waiting guests count toward the hold check.
- Promotions view: released staff and waiting guests below the guest list.

## Test scenarios

**Priority**

- A guest is bumped, then a staff member joins, then a pass frees: the staff member
  gets it.
- A and B both have guests bumped, then a pass frees: A's guest gets it.
- A guest is seated, then bumped again: they keep their place.
- One pass frees with a pair alternate and a waiting guest: the guest gets it. Two
  free: the pair gets them.
- A guest added after claiming ranks behind guests already waiting.

**Host actions**

- Releasing a pass cancels a waiting guest and frees only one pass.
- Removing a seated guest gives the pass to the next person, and the host keeps
  their own.
- Removing a guest protects an option 4 host from release at close.
- A name fix keeps the guest's place, and remove then re-add goes to the back.
- Claiming with options 1 or 2 fails when no spare pass exists. Options 3 and 4
  succeed.

**Entry paths**

- A lottery winner's guest with options 1, 2, 3 and 4 when no pass is left.
- A promoted alternate's guest with options 1, 3 and 4 when no pass is left.

**Close**

- Option 3 host: on the guest list alone, and the guest is left off.
- Option 4 hosts A and B with no alternates: B is released, A's guest is seated,
  and A stays.
- Same, with a staff alternate waiting: the alternate gets B's pass, and A is also
  released.
- Option 4 host with nobody to use the pass: released, and the pass goes unused.
- Option 4 alternate at close: one pass free means no promotion, two free means a
  pair.
- Released host: listed under the guest list, and restored by claim time on reopen.
- Each person gets exactly one email at close, including a lottery drawn by the
  close.
- Held show: a promoted alternate is emailed now and their guest confirmation comes
  when the rep sends, and emails 4 and 5 wait.
- Held show with only waiting guests: the emails are held.
- Reopen: waiting guests stay in line and get free passes.

**Pass counts and lifecycle**

- Pass count reduced with a seated option 3 guest: the guest returns to waiting.
- Pass count reduced with the host's pass cut: the request moves with the host.
- Pass count increased: staff first, then guests.
- Host on leave: the guest is skipped and keeps their place.
- Show deleted: waiting guests are cancelled, and the email mentions them.
- Show unpublished then republished: guests keep their place.

**Migration**

- Existing rows convert correctly in both directions.
