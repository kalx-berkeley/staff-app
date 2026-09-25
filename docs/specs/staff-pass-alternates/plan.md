# Implementation Plan: Staff Pass Alternates Queue

## Overview

When every staff pass for a show is held by a staff member, staff can join an
ordered **alternate queue**. Whenever a staff pass frees up (release, guest-
conditional auto-release, capacity increase, lottery result, show reopen), the
queue is drained automatically: the next eligible alternate is promoted to a
real claim and emailed. Lottery losers are enqueued automatically.

Conceptually this is a single stack ordered by "claim time": claims first
(by `claimed_at`), then alternates (by `priority_at`). A freed slot is filled
by the first entry below it.

Scope: **staff passes only** (DJ pass-pair lottery is unchanged).

## Agreed decisions (from grilling session, 2026-09-25)

| # | Decision |
|---|----------|
| Q1 | The join-queue control appears only when every staff pass is held by a staff member (no `available` passes, no guest holds). Until then, claiming works as today, including displacing guest holds. |
| Q2 | Staff seats beat guests. A freed pass goes to the next alternate's own seat. An alternate's +1 gets a pass only if no waiting alternate could use it. Previously bumped guests of existing claimers are never restored. Unused freed passes become `available`. |
| Q3 | Claimers auto-released by a guest bump are **not** enqueued. Their existing release email gains a link to join the queue. |
| Q4 | Auto-promotion continues until the show is `closed`. |
| Q5 | All staff lottery losers (including only-with-guest losers) are enqueued in `entered_at` order with their guest preferences. Loser emails state queue position and that promotion is automatic. |
| Q6 | Capacity increase → promote alternates. Capacity decrease that cuts a claim → that claimer goes to the **top** of the queue (their `priority_at` = original `claimed_at`). |
| Q7 | Editing guest details keeps position. Leaving and rejoining goes to the bottom. |
| Q8 | All staff see the full list: claims, a divider, then numbered alternates in a distinct color. |
| Q9 | Promotions can view the queue and remove entries (no reordering). A removed alternate is emailed, naming the promotions staff member who removed them. Releases done by promotions on someone's behalf trigger promotion. |
| Q10 | Emails: on promotion, and on show close for everyone still waiting ("you did not get a pass"). No email on join or position change. |
| Q11 | Staff passes only. |
| Q12 | Only-with-guest alternates who can't get a pair are skipped but keep their position. |
| Q13 | If an alternate's guest can't get a pass at promotion, the guest request is dropped, and the promotion email says so. |
| Q14 | Reopening a closed show restores the queue in its original order and emails alternates that they're back in line. |
| Q15 | Unpublish: queue retained and frozen (no promotions while draft). Delete: queue cancelled and alternates emailed. **Claimers are also emailed on delete** (new behavior). |
| Q16 | `/staff/my-passes` lists alternate entries with live position and a leave action, in the alternate color. |
| Q17 | Promoted claims look like any other claim. `alternate_promoted` audit event records the trigger. |
| Q18 | A claimer who releases their own pass while alternates wait leaves entirely. The release dialog warns: "Your pass will go to <next alternate>; you can rejoin at the back of the line." |
| Q19 | Amber styling, an explicit "Alternate #N" label, and a divider between claims and alternates. Guest-hold styling unchanged. |
| Q20 | Delete-show email to claimers: show/venue/date, mentions their +1 if any. Respects `email_enabled`. Lottery winners count as claimers. |
| Q21 | No backfill. Auto-enqueue applies only to lotteries run after deploy. |

## Resolved open items

These came up while mapping the decisions onto the code. All four were resolved
with the recommended answer (in **bold**).

1. **Alternates displacing guest holds.** Q1 assumes no guest holds exist while
   alternates wait, but guest holds can reappear. Example: the last promoted
   alternate's +1 gets a pass while an only-with-guest alternate is still
   waiting. Recommendation: **when promoting, an alternate's own seat may displace
   the newest guest hold, as a direct claim can today. An alternate's +1 may only use a truly
   `available` pass.** Displacing a guest hold follows the existing path
   (`_notify_guest_bumped`, auto-release if only-with-guest, which in turn frees another seat).
2. **Which claims a capacity decrease cuts.** `adjust_passes_for_show` currently
   picks guest holds, then claims, at **random**. Under the stack model, the
   latest claims would be cut first. Recommendation: **cut guest holds newest-first,
   then claims newest-first (by `claimed_at`)**, so the cut claimers go to the top
   of the queue in their original order.
3. **Undelete.** `POST /api/shows/{id}/undelete` restores a deleted show to
   draft. Recommendation: **the queue is not restored** (entries are `cancelled`
   and those alternates were already emailed). They can rejoin.
4. **Queue visible with a free pass.** If only only-with-guest alternates are
   waiting and exactly one pass is free, the free pass stays `available` and any
   staff member can claim it directly (Q1). The waiting alternates stay listed.
   Recommendation: **accept this. The list shows whenever it's non-empty. The join
   control follows the Q1 rule.**

## Data model

### New table `staff_pass_alternates` (`models/staff_pass_alternate.py`)

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `show_id` | FK shows.id, indexed | |
| `staff_id` | FK staff.id, indexed | |
| `has_guest` | bool, default false | |
| `guest_name` | str, nullable | |
| `only_attend_with_guest` | bool, default false | |
| `priority_at` | DateTime(tz), not null | **Ordering key.** Join time for manual joins, `entered_at` for lottery losers, the original `claimed_at` for claims cut by a capacity decrease. Ties are broken by `id`. |
| `source` | str | `joined`, `lottery`, `capacity_cut` |
| `status` | str | `waiting`, `promoted`, `left`, `removed`, `expired` (show closed), `cancelled` (show deleted) |
| `promoted_pass_id` | FK passes.id, nullable | Set on promotion |
| `resolved_at` | DateTime(tz), nullable | When status left `waiting` |
| `removed_by_staff_id` | FK staff.id, nullable | Promotions remover (Q9) |
| `created_at` / `updated_at` | DateTime(tz) | Match `LotteryEntry` conventions |

- Partial unique index on `(show_id, staff_id) WHERE status = 'waiting'`
  (`sqlite_where` + `postgresql_where`).
- Relationships: `Show.alternates` (back_populates), `staff`, `removed_by`.
- Proxy properties like `LotteryEntry` (`staff_name`, `show_event_name`,
  `show_date`, `show_venue_name`).
- Position is **computed** (the index in the ordered `waiting` list), not stored.
  This way, leaving or promoting shifts everyone up without writes.
- Alembic migration with `down_revision = "5f2b6e8a1c4d"` (current head).

No changes to `passes`. A promoted alternate becomes an ordinary claimed `Pass`.

## Backend

### New `services/alternate_service.py` (`AlternateService`)

Core entry point, called from every place that can free a staff pass:

```python
AlternateService.fill_open_passes(db, show, trigger: str, actor_email: str | None) -> list[Promotion]
```

- No-op unless `show.status == "published"` and no lottery is active.
- Does **not** commit. The caller commits with its own change, so the invariant
  holds atomically. Emails and audit entries are returned and sent after the commit.
- Algorithm, mirroring the two-loop design in `_run_staff_lottery`. Repeat until a
  full pass makes no change (guest-hold displacement can cascade):
  1. **Staff seats, unconditional alternates.** In queue order, each waiting
     alternate with `only_attend_with_guest=False` takes a seat. The seat comes from
     an `available` staff pass if there is one, otherwise from displacing the newest
     guest hold (open item 1).
  2. **Pairs for only-with-guest alternates.** This step is reached only once every
     unconditional alternate is served. In queue order, promote an alternate only if
     **two** truly `available` passes exist. Otherwise skip them and keep their place
     (Q12). (Refined during implementation: displacing another claimer's guest to
     seat an only-with-guest alternate would just swap an earlier guest for a later
     one, and would contradict the existing lottery behavior.)
  3. **Guests of this round's promotions.** Leftover `available` passes go, in queue
     order, to the +1 of alternates promoted in step 1 who asked for one. The rest
     have their guest request dropped (Q13).
- Promotion reuses a new internal helper extracted from
  `PassService.claim_staff_pass` (`_assign_claim(db, pass, staff_id, ...)` and
  `_assign_guest_hold(...)`), so claim and promotion share field-setting code.
- Row locking: wrap in the same transaction as the triggering change. SQLite
  serializes writers, and `with_for_update()` on passes/alternates keeps
  Postgres correct if the database changes later.

Other methods:

- `is_queue_open(db, show)`: published, lottery not active, zero `available`
  staff passes, zero guest holds.
- `get_queue(db, show)`: ordered waiting entries plus a computed
  `next_candidate_staff_id` (who step 1/2 would promote next), used for the release warning.
- `join(db, show, staff, has_guest, guest_name, only_attend_with_guest)`: validates
  that the queue is open, the staff member has no claim on this show, and has no waiting
  entry. Applies the venue's `staff_guest_requires_name` rule. Sets `priority_at=now`.
- `update_guest(db, entry, ...)`: `priority_at` unchanged (Q7).
- `leave(db, entry)` → `left`.
- `remove(db, entry, promotions_staff)` → `removed` and emails the alternate (Q9).
- `enqueue_lottery_losers(db, show, entries)`: `priority_at = entered_at`,
  `source="lottery"`.
- `enqueue_cut_claim(db, show, pass_item)`: `priority_at = claimed_at`,
  `source="capacity_cut"`, keeps guest preferences.
- `expire_on_close(db, show)`: waiting → `expired`, emails each (Q10).
- `restore_on_reopen(db, show)`: `expired` → `waiting`, runs `fill_open_passes`,
  emails "you're back in line" with the new position (Q14).
- `cancel_on_delete(db, show)`: waiting/expired → `cancelled`, emails each (Q15).

Emails live in the service, each checking `NotificationPreferences.email_enabled`
the same way `lottery_service.py` does, with links built from
`settings.frontend_base_url` + `/pass-giveaway/staff/shows/{id}`:

- Promoted: says the pass is theirs, and whether the +1 got a pass or the request
  was dropped. Includes a link to release it if they can't attend.
- Removed by promotions: names the remover.
- Show closed, no pass.
- Show reopened, back in line at position N.
- Show deleted, alternate entry cancelled.

### Changes to existing code

- **`PassService.release_claim`**: after freeing the pass and its guest hold, call
  `fill_open_passes(trigger="release")` before commit. Return promotions so the
  router sends emails and audit entries after commit.
- **`PassService.claim_staff_pass`**, guest-hold displacement branch: when the displaced
  primary is auto-released (only-with-guest), call
  `fill_open_passes(trigger="guest_conditional_release")`. Add the join-queue link to
  the `released=True` text in `_notify_guest_bumped` (Q3).
- **`PassService.adjust_passes_for_show`**:
  - Increase: after creating passes, `fill_open_passes(trigger="capacity_increase")`.
  - Decrease: switch selection from random to newest-first (open item 2). Each cut
    primary claim → `enqueue_cut_claim`. Guest holds that were cut are not enqueued.
  - Only-with-guest primaries released because their guest was cut: treat as Q3
    (not enqueued, email gets the join link).
- **`LotteryService._run_staff_lottery`**: after winners and losers are settled,
  `enqueue_lottery_losers` (all `lost` entries in `entered_at` order), then
  `fill_open_passes(trigger="lottery")` to pick up passes returned by case-7
  entrants. Build emails after that:
  - Loser cases 2, 5, 7 and 8 gain "You are alternate #N; if a pass frees up it will be
    assigned to you automatically and you'll be emailed."
  - A loser who is promoted in the same run gets the promotion email instead of the
    loser email.
- **Show close side effects**: `close_show` side effects are currently duplicated in
  `routers/shows.py:close_show` and two places in `scheduler.py`, each calling
  `_notify_staff_guests_confirmed`. Consolidate them into one
  `ShowService.run_close_side_effects(db, show)` that sends the guest-confirmed emails
  and calls `expire_on_close`. Use it in all three places so auto-close can't miss the
  alternates.
- **`routers/shows.py:reopen_show`**: call `restore_on_reopen`.
- **`routers/shows.py:publish_show`**: call `fill_open_passes(trigger="publish")` so a
  republished show (after unpublish) catches up.
- **`ShowService.delete_show`**: `cancel_on_delete`, plus a new claimer cancellation
  email (Q20). Claimed primaries only, not guest holds; mentions the guest name.
- **`routers/passes.py:release_claim`**: send promotion emails and write
  `alternate_promoted` audit entries after commit. Promotions releasing on someone's
  behalf follows the same path (Q9).
- **Direct claim guard** (`routers/passes.py:claim_pass`): unchanged, except it still
  goes through `claim_staff_pass`. No available passes means the UI shows the join
  control instead.

### New router `routers/alternates.py` (prefix `/api/shows`, like `lottery.py`)

| Method & path | Who | Purpose |
|---|---|---|
| `GET /api/shows/{show_id}/alternates` | staff + promotions | `{queue_open, entries: [{id, position, staff_id, staff_name, has_guest, guest_name, only_attend_with_guest}], next_candidate_staff_id}` |
| `POST /api/shows/{show_id}/alternates` | staff | Join. Body matches the claim/lottery entry body. |
| `PATCH /api/shows/{show_id}/alternates/me` | staff | Edit guest details |
| `DELETE /api/shows/{show_id}/alternates/me` | staff | Leave |
| `DELETE /api/shows/{show_id}/alternates/{entry_id}` | promotions | Remove, emailing the alternate with the remover's name |
| `GET /api/shows/alternates/my-entries` | staff | For My Passes: waiting entries with position and show info |

Register the router in `main.py` and add `/api/shows` → `routers/alternates.py` to the
routing map in `CLAUDE.md`. Route ordering: declare `alternates/my-entries` before
`/{show_id}` patterns, as `lottery.py` does for `lottery/my-entries`.

Schemas go in `schemas/alternate.py`: `AlternateJoinRequest`, `AlternateUpdateRequest`,
`AlternateEntryResponse`, `AlternateQueueResponse`, `MyAlternateEntryResponse`.

### Audit events

`alternate_joined`, `alternate_updated`, `alternate_left`, `alternate_removed`,
`alternate_promoted` (details: `show_id`, `pass_id`, `trigger`, `triggering_pass_id`
/ actor, `guest_granted`), `alternates_enqueued_from_lottery`,
`alternates_expired`, `alternates_restored`, `alternates_cancelled`.

## Frontend

- **`types/index.ts`**: `AlternateEntry`, `AlternateQueue`, `MyAlternateEntry`.
- **`services/api.ts`**: `alternatesAPI` (get, join, update, leave, remove,
  myEntries).
- **`components/staff/ShowDetail.tsx`**:
  - Fetch the queue alongside passes and refresh it after every claim, release or join action.
  - When `queue_open` and the user has no claim and no entry: show a **Join as
    alternate** form, reusing the claim form's +1 / guest name / only-with-guest
    controls, with copy explaining that promotion is automatic and that staff
    come before guests.
  - Claims list: current claims, then a divider labeled "Alternates", then amber
    rows labeled `Alternate #N`, with the current user's row highlighted. When there are
    entries, show a note such as "N people are ahead of you."
  - The user's own entry has Edit guest and Leave queue actions.
  - Release confirmation: when `next_candidate_staff_id` is set, show "Your pass will
    go to <name>; you can rejoin at the back of the line."
  - Alternate styling uses CSS variables or a shared class so My Passes matches.
- **`components/promotions/ShowDetail.tsx`**: a read-only alternates section with
  the same styling, plus a Remove action with a confirmation dialog.
- **`components/staff/MyPasses.tsx`**: an "Alternate" section listing waiting
  entries (show, date, venue, `Alternate #N`, guest info), with a Leave action.

## Tests

Backend, in the `tests/test_alternates.py` pytest style of `test_passes.py` / `test_lottery.py`:

- The queue opens only when there are no available passes and no guest holds. Joining is rejected otherwise, when already claimed, or when a duplicate entry exists.
- Release promotes #1. Positions shift. The promoted pass has the right `staff_id` and `claimed_at`.
- Only-with-guest #1 is skipped for a single freed pass, and #2 is promoted. #1 gets a pair when they're the only one left and two passes are free.
- A promoted alternate with has_guest gets a guest hold only when nobody else is waiting. Otherwise the guest is dropped, and the email says so.
- Cascade: a promotion displaces a guest hold, which auto-releases an only-with-guest claimer, which frees a seat for the next alternate.
- A guest-conditional auto-release triggers promotion, and the released user's email contains the join link.
- Capacity increase promotes. Capacity decrease cuts claims newest-first, and the cut claimers go to the top in `claimed_at` order.
- Lottery: losers are enqueued in `entered_at` order with their preferences. Loser email text includes the position. A loser promoted in the same run gets only the promotion email.
- Close expires the queue and emails alternates, from the router and both scheduler paths. Reopen restores the order and emails. Unpublish freezes the queue, and republish fills it. Delete cancels the queue and emails alternates and claimers.
- Promotions removal emails the alternate with the remover's name. Staff can't remove others.
- Edit keeps position. Leave and rejoin puts the user at the bottom.
- `email_enabled=False` suppresses every new email.
- Audit events are written with the correct triggers.

Frontend (Vitest, extending `staff/ShowDetail.test.tsx`, `MyPasses` tests and
`promotions/ShowDetail.test.tsx`):

- The join form is hidden while passes are available and shown when `queue_open`.
- Alternates render after the divider with the `Alternate #N` label and styling.
- The release warning names the next candidate.
- My Passes lists alternate entries and the Leave action.
- The promotions Remove action calls the API.

## Suggested task order

1. Model, migration, schemas.
2. Extract `_assign_claim` / `_assign_guest_hold` from `claim_staff_pass`
   (a refactor with no behavior change; existing tests must still pass).
3. `AlternateService` core: join/leave/update/remove, `get_queue`,
   `fill_open_passes`, plus unit tests for the algorithm.
4. Wire the triggers: release, guest-conditional release, adjust passes, publish.
5. Lottery integration and updated loser emails.
6. Show lifecycle: consolidate close side effects, reopen, delete (including the
   claimer email).
7. `routers/alternates.py`, audit events, `CLAUDE.md` routing map.
8. Frontend: types/API, staff ShowDetail, promotions ShowDetail, My Passes.
9. Manual end-to-end check using the `run-staff-app` skill (multiple staff via
   `X-Forwarded-User`).
10. CHANGELOG entry.
                                                                                                                                                                                                                                                                                                                                                                                                                                 