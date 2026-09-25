# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Common Changelog](https://common-changelog.org/).

---

## [Unreleased]

### Added

- Add a staff-pass alternate list: once every staff pass is held by a staff member, staff can join an ordered alternate list (with the same +1 guest options as a claim), and freed passes are assigned to the next alternate automatically with an email notification
- Queue staff lottery losers as alternates in the order they entered, and state their alternate position in the lottery result email
- Show alternates under a show's staff pass claims, and on My Passes, in amber with an "Alternate #N" label; promotions staff can remove alternates, who are emailed
- Email alternates when a show closes without them getting a pass, when a reopened show puts them back in line, and when a show is deleted
- Email staff pass holders when a show is deleted
- Email staff whose pass is removed by a pass-count reduction, with their new alternate position

### Changed

- Cut the newest guest holds and then the newest staff claims (instead of random ones) when a show's pass count is reduced, and move cut claimers to the top of the alternate list
- Link to the show's page from the email sent when a staff pass is released because its +1 guest was bumped
- Only let staff release their own staff pass: the Release button now appears only on your own claim, and the API rejects staff releasing someone else's (promotions staff can still release any claim)

### Fixed

- Show claim and giveaway times in Pacific time on the staff show page, staff and DJ My Passes, and the staff lottery deadline, matching the promotions and DJ show pages instead of the viewer's browser timezone

## [1.3.0] - 2026-09-19

### Changed

- Show names instead of raw emails for users and owners across the staff app UI — the impersonate-user dropdown, owner lists (now mailto-linked), and the navigation pane's current/impersonated user display ([7aa4b64](https://github.com/kalx-berkeley/staff-app/commit/7aa4b64))
- Return every current spin/show match on each DJ poll instead of marking it delivered the moment it's computed, and let the DJ view dismiss each match explicitly per show ([8ab9b83](https://github.com/kalx-berkeley/staff-app/commit/8ab9b83))
- Highlight only DJ pre-assigned shows airing today; other pre-assigned shows render dimmed ([31202ed](https://github.com/kalx-berkeley/staff-app/commit/31202ed))
- Standardize button styling (primary/secondary/danger) across staff and promotions views ([d420cf5](https://github.com/kalx-berkeley/staff-app/commit/d420cf5))
- Move the "cannot pre-assign to own DJ name" error message to a clearer spot on the page ([66eb792](https://github.com/kalx-berkeley/staff-app/commit/66eb792))
- Show which tagged band a KALX Live! appearance is for and update the badge icon ([53be60b](https://github.com/kalx-berkeley/staff-app/commit/53be60b))
- Move `KALX_LIVE_CALENDAR_ID` from a GitHub Actions secret to a variable ([d63d680](https://github.com/kalx-berkeley/staff-app/commit/d63d680))

### Added

- Add a KALX Live! badge and popup that matches show artists against the public KALX Live! performance calendar via a nightly sync ([a7aad0f](https://github.com/kalx-berkeley/staff-app/commit/a7aad0f))
- Add the number of days until or since a KALX Live performance ([847f14a](https://github.com/kalx-berkeley/staff-app/commit/847f14a))
- Allow tagging show-name artists that have no MusicBrainz match ([147a558](https://github.com/kalx-berkeley/staff-app/commit/147a558))
- Add a shared `PersonAutocomplete` component and use it for owner fields on the venue form, promoter form, and specialty show detail ([7bfdb5c](https://github.com/kalx-berkeley/staff-app/commit/7bfdb5c))
- Add read-only viewing of specialty shows for non-owner staff, with a DJ badge and owner-email autocomplete ([f6155ae](https://github.com/kalx-berkeley/staff-app/commit/f6155ae))
- Add a specialty shows section, with Owner/DJ badges, to staff and promotions profile pages via a new `GET /api/specialty-shows/mine` endpoint ([fe2b8e4](https://github.com/kalx-berkeley/staff-app/commit/fe2b8e4))
- Add a current-view indicator to the navigation UI so users can see which of Promotions, Staff, or DJ they're in ([efe4943](https://github.com/kalx-berkeley/staff-app/commit/efe4943))
- Add a page indicator to the navigation pane highlighting the active page within a view ([f7fd7a9](https://github.com/kalx-berkeley/staff-app/commit/f7fd7a9))
- Give each page a descriptive browser tab title ([d6b7789](https://github.com/kalx-berkeley/staff-app/commit/d6b7789))
- Tag staging email subjects and bodies with `[STAGING]` when `ENVIRONMENT=staging` ([be414ef](https://github.com/kalx-berkeley/staff-app/commit/be414ef))
- Add a `--dj-name` argument to `test_user.py` ([a3e4f25](https://github.com/kalx-berkeley/staff-app/commit/a3e4f25))
- Add a `--sublist-dj` flag to `test_user.py create` ([4495218](https://github.com/kalx-berkeley/staff-app/commit/4495218))
- Add a script to create and delete staging test users ([72df53c](https://github.com/kalx-berkeley/staff-app/commit/72df53c))
- Add a script to mask phone numbers in staging ([4073263](https://github.com/kalx-berkeley/staff-app/commit/4073263))

### Fixed

- Fix staff pass guest-hold bumping and allow only one staff pass per show per staff member; the Claim button now disables once the current user already holds a pass ([205542d](https://github.com/kalx-berkeley/staff-app/commit/205542d))
- Exclude deactivated staff from the impersonation dropdown and the venue/promoter owner pickers ([5e4b0ac](https://github.com/kalx-berkeley/staff-app/commit/5e4b0ac))
- Fix the wrong domain in auto-close notification links, which pointed at a `kalx.berkeley.edu` fallback the app is never served from ([be414ef](https://github.com/kalx-berkeley/staff-app/commit/be414ef))
- Fix "past" mislabeling of scheduled lottery and auto-close jobs, and stop startup job restoration from skipping shows with no entries yet ([ff5bf41](https://github.com/kalx-berkeley/staff-app/commit/ff5bf41))
- Fix closed shows showing guest-hold staff passes as "Available" and allowing DJ pass-pair pre-assignment after the show closed ([4ef7670](https://github.com/kalx-berkeley/staff-app/commit/4ef7670))
- Refresh lottery status immediately after publish, unpublish, or reopen instead of showing stale status until the next full page load ([580cdcc](https://github.com/kalx-berkeley/staff-app/commit/580cdcc))
- Deactivate staff who are removed from Airtable instead of leaving their access in place indefinitely ([9165e4a](https://github.com/kalx-berkeley/staff-app/commit/9165e4a))
- Fix single-word artist and band names (e.g. "Trough") being silently excluded from KALX Live! and feature-bin matching, and extend the fix to Spinitron spin matching via a shared fuzzy-matching module ([5deab07](https://github.com/kalx-berkeley/staff-app/commit/5deab07))

## [1.2.0] - 2026-09-12

### Changed

- Replace native `<input type="date">` app-wide with a shared `react-day-picker` component; allows free-text date entry.
- Eliminate remaining full-page reloads on staff pass actions (claim, release, lottery enter/withdraw, pre-assign, remove) in favor of silent/local-state refreshes.
- Extend Spinitron forward-search window from 4 to 8 weeks; schedule lookups now consult both `/shows` and `/playlists` to catch pre-provisioned slots that `/shows` still shows as a placeholder DJ.
- Upgrade backend and frontend dependencies (pytest/httpx migration, vitest 4→5, testing-library 6→7, npm audit fix); hold TypeScript and jsdom back pending compatible tooling.
- Deduplicate near-identical code in `UserService`, `SpinitronService` pagination, and `SpecialtyShowDetail`'s save handlers.
- Improve Spinitron user-agent string, spin-match popup UI, and feature-bin fuzzy matching.

### Added

- Feature bin flags — shows are flagged on promotions/staff/DJ views when a performing artist has a new release in KALX's "feature bin," synced nightly from a Google Sheet, with a badge popup showing album/date/listen link.
- Spinitron-backed on-air awareness:
  - Auto-fills, validates, and auto-advances the DJ Name field from the live on-air schedule.
  - Restricts pass-pair reservation dates to a DJ's/specialty show's actual on-air schedule (with override).
  - Notifies DJs on-air when a played song matches a giveaway show, via a polled spin-matches endpoint.
  - Autocompletes for specialty show names and DJ history when building a roster.
  - Admin "Scheduled Jobs" panel can now manually clear/refresh the cached Spinitron schedule.
- Genre preferences & DJ suggestions — staff can set genre preferences; promotions gets a "Suggest DJ" flow on pre-assignment, by on-air date or by genre match.
- Content warnings — flags non-value-neutral language (praise, calls to action, "ticket" vs. "pass") in on-air descriptions.
- Add a LICENSE file and document app features in the README.
- Add a deploy script for faster test deployments.

### Fixed

- Sublist DJ status was missing from promotions-role staff responses, silently hiding the pass-pair reservation section for those users.
- 500 error on specialty-show DJ history lookback (was querying `/shows`, which rejects dates >1hr in the past; now uses `/playlists`).
- Several DJ pre-assignment schedule bugs: timezone bucketing (UTC vs. Pacific calendar day), redundant duplicate requests, and date-picker UX.
- Pre-assign close-date bound used the wrong date field (`show_date` instead of `planned_close_date`).
- `act()` warnings in tests rendering `DjNameInput`/`ShowForm`.
- Impersonation identity resolution was inconsistent across genre/notification preferences, show visibility, and pre-assignment audit attribution; also fixed `GenreTagInput` losing focus after each addition.

## [1.1.0] - 2026-09-10

### Changed

- Unified profile settings — promotions and staff profile pages now share a single `ProfileSettings` component (previously two near-duplicate implementations), removing ~270 lines of duplicated code.
- DJ pass-pair lottery calendar — date pickers for DJ pass-pair reservations now enforce the lottery blackout window (`dj_preassign_prohibition_days` before the planned close date) directly as the date input's max value, instead of only showing a warning after the fact. The lottery reservation form was also restyled to match the pass-card layout used elsewhere.

### Added

- Notification audit trail — email audit log entries on `/promotions/admin` now record whether a send actually succeeded, plus the mail server's response details (status code, request ID, email ID for smtp2go; host/port/refused recipients for local SMTP) or the specific error on failure. Previously, failed sends left no audit trail at all.
- Build info link — every layout (staff, DJ, promotions) now shows a link to build/version information, later moved from the top nav to the bottom of the page for less clutter.
- Notification preferences explainer — the profile page's email-notification toggle now lists exactly what it covers (lottery results, entry cancellations, venue-owner alerts) so users know what they're opting out of.
- MusicBrainz search feedback — the band annotator's MusicBrainz search now shows a loading indicator so users know a search is in progress rather than looking frozen.

### Fixed

- Staging nav scrolling — fixed a scrolling bug in the navigation bar on the staging site.

## [1.0.0] - 2026-09-10

_Initial production release._

[1.3.0]: https://github.com/kalx-berkeley/staff-app/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/kalx-berkeley/staff-app/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/kalx-berkeley/staff-app/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/kalx-berkeley/staff-app/releases/tag/v1.0.0
