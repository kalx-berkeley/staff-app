# Implementation Plan: KALX Staff Analytics improvements

## Overview

A round of changes to KALX Staff Analytics (`/analytics/`), mostly to the
Radio Pass Giveaway's metrics: one date rule for every pass giveaway metric,
a "This month" default window, an "announced" measure of how many shows get
mentioned on air, a new On-air winners tab with a page per winner, per-column
ⓘ explanations, and shareable section links.

Builds on `docs/analytics/specs/analytics-site/plan.md`; where the two
disagree, this plan wins (its decision Q3 is replaced by Q1 below).

Terms:

- **Announced show**: a complete show (closed, or with a show date before
  today) with at least one pass pair given away or at least one "tried" click.
- **Announced % (shows)**: announced shows ÷ complete shows.
- **Announced % (one show)**: (pass pairs given away + "tried" clicks) ÷ pass
  pairs. Each extra try adds to it, so it can be over 100%.
- **Winner**: a phone number, or the numbers of a linked caller (as in Linked
  Callers).
- **Block**: a win-limit warning, counted once per (phone, show, Pacific day).

## Agreed decisions (from grilling session, 2026-11-28)

| # | Decision |
|---|----------|
| Q1 | Every pass giveaway metric places what it counts by the **show date** of the show it belongs to: giveaways, tries, page visits, popups, wins, win-limit warnings and overrides, staff pass claims. Short Links and site usage metrics still use when it happened. |
| Q1a | A new **"This month"** window is the default (instead of "Last 30 days"). |
| Q2 | Winners a promotions rep enters on the show form count as given away everywhere, like any other giveaway. No special case. |
| Q3 | Announced % counts complete shows only. It's a fifth card on the overview, and replaces "Attempts per giveaway" on the venues table and venue page. |
| Q4 | Per-show announced % on the reps tab is (given + tried) ÷ pairs and may exceed 100%; the ⓘ says why. |
| Q5 | Each winner gets a detail page, `/analytics/winners/:winId`. |
| Q6 | `:winId` is the ID of one of the winner's on-air wins (their latest when linked from the analytics site); the server resolves it to the winner's linked-caller group. No phone number in URLs. |
| Q7 | The On-air winners tab lists every winner with a win in the window, and a "Blocked by the win limit" table. Callers with a block in the window get a detail page even without a win in the window. |
| Q8 | Blocks are counted once per (phone, show, day). From now on win-limit warnings also record the request's network and signed-in user. |
| Q9 | "Top staff pass claimants" rows expand to list the shows each person claimed. |
| Q10 | Every table column gets its own ⓘ except plain name columns (Venue, DJ, Month, Staff member, Show, Name…). Section ⓘs keep the date basis and includes/excludes. Detail sub-tables too. |
| Q11 | Every metric section has an anchor: its metric ID with `_` → `-` (e.g. `#top-djs-given-tried`). Headings get a `#` link that copies the full URL (window included). The page scrolls to it once loaded, and a collapsed table that's linked to opens. |
| Q12 | "This month", "This quarter" and "This year" run to the end of the period, so upcoming shows' activity counts as it happens. "Last 30 days" ends today. |
| Q13 | Names in the repeat winners table and the winner list link to the winner page. "Similar names, different phones" keeps linking to Promotions → Admin → Linked Callers. |
| Q14 | "Blocked by the win limit" lists every block with an Outcome: **Overridden** (an override was recorded for that show and phone), **Won with another number** (someone with a similar name won that show on a different number after the block), else **Blocked**. Blocked and Won-with-another-number rows are highlighted. |
| Q15 | The winner page shows cards (wins in window, wins all time, blocks), every win at any time with the window's highlighted, their blocks, their linked numbers, and a link to Linked Callers. |
| Q16 | The tab is "On-air winners", at `/analytics/winners`, between DJs and Promotions reps. Winner list columns: Name, Phone, Wins (window), Wins (all time), Venues, Last won, Blocks. |

Also agreed (no question needed):

- Remove "Top DJs by pass pairs given away" and "Utilization by promoter".
- Move the winner metrics (top repeat winners, wins going to repeat winners,
  similar names) from the overview to the On-air winners tab.
- The popup table's ⓘ explains "Ignored": the DJ neither dismissed it (the ×)
  nor clicked through; it went away by itself 15 minutes after the song's
  spin, or when the show stopped being one they could give away.
- Table headers wrap.
- Balance (`points`) columns are left-aligned, header included; the venue
  page's balance card no longer overflows.
- Median lead time and median time to first giveaway show whole days.
- DJs tab: a "Given away + tried" column after "Tried".

## Implementation

Backend:

- `analytics_window.py`: `this_month` preset (default); `this_*` presets end
  at the period's end.
- `analytics_metrics.column()` takes `help=`; the frontend shows it as the
  column's ⓘ.
- `pass_giveaway/analytics.py`: load giveaways, attempts, visits, popups,
  wins, warnings and claims by their show's date; the new metrics; the
  `winners` and `winner` metric groups (new `TABS` entries).
- `pass_giveaway/routers/passes.py` (`check-winner`): add `network` and the
  signed-in user to the `winner_frequency_warning` details.

Frontend (`frontend/src/analytics/`):

- `MetricTable`: wrapping headers, column ⓘ, left-aligned points columns.
- `MetricView`: section anchor and copy-link `#` on every heading;
  `TabPage` scrolls to the hash after loading; a linked collapsed table opens.
- Routes and tab for `/winners` and `/winners/:winId`; `timeWindow.ts`
  default `this_month`.
