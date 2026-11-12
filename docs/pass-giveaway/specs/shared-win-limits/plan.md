# Implementation Plan: Shared Win Frequency Limits

## Overview

Some venues are owned by the same company, and the company doesn't want the
same on-air winner winning at one of its venues one week and at another the
next. Today each venue's Win Frequency Limit only looks at wins at that venue,
so a listener can win at Elmwood on day 1, Cerrito on day 20, Elmwood on day 40
and Cerrito on day 60 without breaking either venue's 30-day limit.

This feature lets a promotions rep mark a venue (Cerrito) as sharing another
venue's (Elmwood's) win frequency limit. Elmwood is the **parent** and Cerrito
a **child**. The parent's limit applies to the whole **family** (the parent
plus its children): a winner is checked against their most recent win at any
venue in the family.

Design agreed 2026-11-12.

## Decisions

| # | Question | Decision |
|---|---|---|
| 1 | Data model | A nullable `venues.parent_venue_id` pointing at another venue. The parent's `win_frequency_days` is the family's limit. |
| 2 | Depth | One level only. A parent can't be a child, a venue with children can't pick a parent, and a venue can't pick itself. Enforced by the backend as well as the form. |
| 3 | A child's own limit | Saving a venue as a child clears its `win_frequency_days`. The backend refuses a limit on a child. The form replaces the limit field with read-only text, e.g. "Uses Elmwood's limit: 30 days". |
| 4 | Parent with no limit | Allowed. No limit for the whole family. The child's form says "Elmwood has no win frequency limit". |
| 5 | Where the link is set | Only on the child's form. |
| 6 | DJ view | The banner names the sister venues ("This venue limits winners to once every 30 days (shared with Cerrito)."), listing only the other venues, never the current one. The ineligible warning names the venue of the previous win. |
| 7 | Deleting a parent | Blocked while it has children (409, naming them). |
| 8 | Retroactivity | The family is worked out at check time. Linking makes past wins count straight away; unlinking makes them stop. No history of links. |
| 9 | Parent's form | Shows a read-only "Also applies to: Cerrito" list next to its limit field, linking to each child's edit page. |
| 10 | Analytics flag | The overview's "same name, different phones" table groups wins by family and uses the parent's limit. Its column becomes "Same venue or sister venue within limit". |
| 11 | Per-venue analytics pages | Unchanged: each venue page shows only that venue's wins. |
| 12 | Audit log | `winner_frequency_warning` and `venue_frequency_override` also record `last_win_venue_id` and `last_win_venue`. They stay credited to the venue where the giveaway happened. |
| 13 | One check | The `check-winner` route calls `PassService.find_win_frequency_conflict`, so the family logic exists once. |
| 14 | Show payload | The show's `venue.win_frequency_days` is the effective (family) limit, plus a new `win_frequency_shared_with` list of sister venue names. |
| 15 | Deleting a child | Unlinks it right away; its past wins stop counting against the family. |
| 16 | Restoring a deleted child | Comes back with no parent and no limit, with no special warning. |
| 17 | Forms | The field is on both the New Venue and Edit Venue forms (`VenueForm`). |
| 18 | Field name | "Shares a win frequency limit with", a dropdown of venues plus "None". |
| 19 | Audit on unlink | `venue_deleted` records `unlinked_from_parent_venue_id` and `unlinked_from_parent_venue` when deleting a child unlinks it. Link changes on edit appear in `venue_updated`'s `changed_fields` as `parent_venue_id`. |

## Data model

- Add `venues.parent_venue_id` (Integer, nullable, foreign key to
  `venues.id`) in a new Alembic migration.
- `Venue.parent` and `Venue.children` relationships. `children` includes
  deleted venues only in theory: deleting a child unlinks it (decision 15), so
  every child is live.
- Helpers on `Venue`:
  - `limit_venue`: the parent if there is one, otherwise the venue itself.
  - `effective_win_frequency_days`: `limit_venue.win_frequency_days`.
  - `family_venue_ids`: the limit venue's ID plus its children's IDs.
  - `sister_venue_names`: the family's other venues' names, sorted.

## Backend

- **Schemas** (`pass_giveaway/schemas/venue.py`): `parent_venue_id` on
  `VenueCreate`, `VenueUpdate` and `VenueResponse`. `VenueResponse` also gets
  `parent_venue_name`, `children` (id and name, for decision 9) and
  `effective_win_frequency_days`.
- **Validation** (`VenueService`, create and update): the parent must exist,
  not be deleted, not be the venue itself and not have a parent; the venue
  must not have children. A child with a non-null `win_frequency_days` is a
  400. Setting a parent clears the venue's own limit.
- **Delete** (`VenueService.delete_venue`): 409 when the venue has children;
  a child is unlinked and the delete route's audit entry names the former
  parent.
- **Update audit** (`routers/venues.py`): `parent_venue_id` joins the
  before/after snapshot.
- **Check** (`PassService.find_win_frequency_conflict`): filter
  `OnAirWinner.venue_id.in_(family_venue_ids)` and use the effective limit.
  Return the earlier win's show name, date and venue. The `check-winner` route
  calls it and builds its response and `winner_frequency_warning` entry from
  the result.
- **Show payload** (`routers/shows.py`): `win_frequency_days` becomes the
  effective limit; add `win_frequency_shared_with`.
- **Analytics** (`pass_giveaway/analytics.py`): `_bypasses_win_limit` groups
  wins by family ID (the limit venue's ID) and uses the family limit. The
  venue page keeps passing only its own venue.

## Frontend

- **Types** (`pass-giveaway/types.ts`): the new venue fields and the show's
  `win_frequency_shared_with`; `last_win_venue` on the eligibility result.
- **VenueForm**: a "Shares a win frequency limit with" select (live venues
  that have no parent, minus this venue; disabled with an explanation when
  this venue has children). When a parent is chosen, the limit input is
  replaced with the read-only text from decisions 3 and 4. The parent's form
  shows "Also applies to:" with links to its children.
- **PassGiveawayForm / WinnerEditForm**: the banner and warning text from
  decision 6.

## Tests

- Backend: validation rules, clearing the limit, delete blocking and unlinking
  with the audit details, the family check (giveaway, correction and
  `check-winner`), the show payload, and the analytics flag.
- Frontend: VenueForm's select, read-only limit text and children list; the DJ
  banner and warning naming sister venues.
