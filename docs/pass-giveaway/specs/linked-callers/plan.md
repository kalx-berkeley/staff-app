# Implementation Plan: Linked Callers

## Overview

A venue's Win Frequency Limit is checked against the phone number the DJ
types in. A caller who gives a different number each time gets around it:
John Doe wins The Arena on June 15th with 212-555-5555, then calls in with
212-888-8888 and nothing connects the two.

KALX Staff Analytics already lists on-air winners with similar names and
different phone numbers ("Similar names, different phone numbers"). This
feature lets a promotions admin confirm that some of those numbers belong to
one person, a **linked caller**. From then on a win on any of the caller's
numbers counts against the limit for all of them: when John Doe calls in again
with 212-888-8888 for Glitch Mob at The Arena on June 20th, the DJ's giveaway
page warns that he won at The Arena 5 days earlier.

Design agreed 2026-11-21.

## Decisions

| # | Question | Decision |
|---|---|---|
| 1 | What is linked | Phone numbers. A caller (`on_air_callers`) has two or more normalized phone numbers (`on_air_caller_phones`); a number belongs to at most one caller. Wins follow their numbers. |
| 2 | Where | A "Linked Callers" section on Promotions → Admin (`/pass-giveaway/promotions/admin#linked-callers`). KALX Staff Analytics stays read-only and links rows there. |
| 3 | Who | Promotions admins and site admins (`get_site_or_promotions_admin`). Every change is audit-logged under the pass giveaway area. |
| 4 | Suggestions and manual links | The section suggests similar-name groups (`caller_names.group_similar_names`, the analytics grouping), and also has a search for any winner by name or phone, so nicknames the matcher misses can be linked by hand. |
| 5 | Not the same person | Dismisses the group as it stands, stored as pairs of numbers (`dismissed_caller_pairs`). A win on a new number brings the group back with just the new number's pairs unresolved. A dismissal can be undone. |
| 6 | Undo | A number can be removed from a caller, or the whole caller unlinked. A caller left with one number is deleted. Unlinking only changes future checks. |
| 7 | DJ warning | When the earlier win was on another linked number, the warning adds "This was under another phone number linked to this caller." It never shows that number. `winner_frequency_warning` and `venue_frequency_override` record `matched_phone`. |
| 8 | Too common a name | Marked per normalized name (`common_caller_names`). A suggested group containing a marked spelling is hidden from suggestions. Manual linking still works. Marked names are listed and can be unmarked. |
| 9 | Dismissal granularity | "Not the same person" on a group stores every pair of its numbers that aren't already in the same caller. |
| 10 | Merging | Linking a number that's already in another caller merges the callers, after a confirmation listing every number that ends up together. One audit event. |
| 11 | Caller note | A caller has an optional note ("same email", "confirmed on air"), editable later. |
| 12 | Which suggestions | All time. Groups that would have broken a venue limit come first. Resolved groups (linked, dismissed, common name) are hidden unless "Show resolved" is on. |
| 13 | Analytics | "Similar names, different phone numbers" gets a Status column (Linked, Partly linked, Dismissed, Common name, Unreviewed) and only unresolved rows are highlighted. "Top repeat on-air winners", "Wins going to repeat winners" and the venue repeat winners table count a linked caller as one person. The ⓘ explanations say so. |
| 14 | Corrected phone numbers | Links stay with numbers, and nothing is added automatically. A linked number with no wins left is shown with a hint ("linked but has no wins any more") so an admin can remove it. |
| 15 | Layout | A section on the Admin page, not its own page. |
| 16 | Manual link vs. dismissal | A link deletes the dismissed pairs among its numbers, recorded in the same audit entry. Unlinking doesn't bring them back. |
| 17 | Analytics links | Each name in those analytics tables links to `/pass-giveaway/promotions/admin?caller=<name>#linked-callers`, which shows that name's group (resolved or not) and its callers. Analytics and the section have the same audience. |

## Data model

New Alembic migration, models in `backend/app/models/on_air_caller.py`:

- `on_air_callers`: `id`, `note` (nullable text), `created_at`, `updated_at`.
- `on_air_caller_phones`: `phone` (primary key, normalized digits),
  `caller_id` (FK, cascade delete), `linked_at`.
- `dismissed_caller_pairs`: `phone_a`, `phone_b` (composite primary key,
  `phone_a < phone_b`), `dismissed_by`, `dismissed_at`.
- `common_caller_names`: `name` (primary key, `normalize_person_name`
  output), `marked_by`, `marked_at`.

## Backend

- **`pass_giveaway/services/linked_callers.py`**: the linking logic.
  - `linked_phones(db, phone)`: the number plus every number linked to it.
  - `LinkState.load(db)`: callers, dismissed pairs and common names in one
    load, for grouping and analytics. `person_key(phone)` gives a caller key
    or the phone itself, and `group_status(phones, names)` gives a group's
    status.
  - `suggestions`, `callers`, `search`, `preview_link`, `link`,
    `unlink_phone`, `unlink_caller`, `update_note`, `dismiss`,
    `undismiss`, `mark_common` and `unmark_common`. Each change writes its
    audit event: `callers_linked` (with `merged_caller_ids` and
    `removed_dismissals`), `caller_phone_unlinked`, `caller_unlinked`,
    `caller_note_updated`, `caller_suggestion_dismissed`,
    `caller_dismissal_undone`, `caller_name_marked_common` and
    `caller_name_unmarked_common`.
  - `venue_win_limits` and `bypasses_win_limit` move here from
    `analytics.py`, so the section and analytics flag groups the same way.
- **Limit check**: `PassService.find_win_frequency_conflict` filters on
  `linked_phones(...)` instead of one number, and adds `matched_phone` and
  `linked_number` to its result. `check-winner` returns `linked_number`.
- **Routes**: `pass_giveaway/routers/callers.py`, prefix
  `/api/pass-giveaway/admin/callers`, `route_class=GuestRedactingRoute`,
  every route `get_site_or_promotions_admin`:

  | Method and path | What |
  |---|---|
  | `GET /suggestions?resolved=&name=` | Similar-name groups with their numbers, wins and status |
  | `GET /` | Linked callers with their numbers (and stale-number flags) |
  | `GET /search?q=` | Winners' numbers matching a name or digits |
  | `POST /preview` | The numbers a link would put together, and the callers it would merge |
  | `POST /` | Link numbers (merging callers), with an optional note |
  | `PATCH /{id}` | Change the note |
  | `DELETE /{id}/phones/{phone}` | Remove one number |
  | `DELETE /{id}` | Unlink the whole caller |
  | `POST /dismissals`, `POST /dismissals/undo` | Not the same person, and undoing it |
  | `GET /common-names`, `POST /common-names`, `DELETE /common-names/{name}` | Too common a name |

- **Analytics** (`pass_giveaway/analytics.py`): repeat winners group by
  `person_key`, the same-name table gets the Status column and highlight
  rule, and names link to the section through a new `external` flag on
  `analytics_metrics.column` (rendered as a plain link outside the analytics
  router).

## Frontend

- `pass-giveaway/promotions/LinkedCallersSection.tsx` on `Admin.tsx`, with
  `callersAPI` in `api.ts` and its types in `types.ts`. It reads `?caller=`
  and scrolls to `#linked-callers`.
  - Suggestions: each group shows its spellings, status, whether it would
    have broken a limit, its wins, and a checkbox per number. Actions: link
    the checked numbers (confirmation with the resulting numbers and a
    note), Not the same person, Name too common; on resolved groups, undo.
  - Search: find winners by name or phone, pick numbers, link them.
  - Linked callers: numbers with names and wins, the stale hint, remove a
    number, edit the note, unlink all.
  - Too common names: the list, with Unmark.
- `dj/PassGiveawayForm.tsx` and `dj/WinnerEditForm.tsx` add the linked-number
  sentence to the warning.
- `analytics/MetricTable.tsx` renders `external` links with `<a href>`,
  URL-encoding the filled values.

## Tests

- Backend `tests/pass_giveaway/test_linked_callers.py`: the John Doe example
  end to end through `check-winner` and the giveaway; linking, merging,
  removing, unlinking, notes, dismissing (and a new number reopening a
  group), common names, search, stale numbers, a link clearing dismissals,
  audit entries and access (staff get 403). Analytics tests for the Status
  column, the highlight rule and repeat winners counting a caller once.
- Frontend tests for the section, the DJ warning sentence and external
  metric links.
