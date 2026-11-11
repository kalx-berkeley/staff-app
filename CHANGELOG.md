# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Common Changelog](https://common-changelog.org/).

---

## [1.13.3] - 2026-11-11

### Fixed

- Fix staging deploys failing for every commit after the first. Staging copied the newest commit on `main` out of the server's copy of the repository without fetching it first, so it couldn't find it. Production deploys weren't affected ([e4bed78](https://github.com/kalx-berkeley/staff-app/commit/e4bed78))

## [1.13.2] - 2026-11-11

### Changed

- Deploy from the server instead of GitHub Actions, so deploys start on time and GitHub has no access to the server. A systemd timer deploys the newest commit on `main` to staging within about 2 minutes of its tests passing, and the newest release to production at 3:51am Pacific. A failed production deploy rolls back to what was live, and failed deploys and production deploys are emailed to `WEBMASTER_EMAIL`. Each environment's settings now live only in its `.env` on the server ([b36e13a](https://github.com/kalx-berkeley/staff-app/commit/b36e13a))
- Run the tests on every push to `main`, including docs-only pushes, since a commit is only deployed once its tests have passed ([b36e13a](https://github.com/kalx-berkeley/staff-app/commit/b36e13a))

### Removed

- Remove the GitHub Actions deploy, including its nightly scheduled run, and `scripts/deploy-staging.sh` ([b36e13a](https://github.com/kalx-berkeley/staff-app/commit/b36e13a))

### Fixed

- Fix the nightly deploy waiting forever, without saying so, for a release whose tests never ran. It now emails instead. This happened to v1.13.1, whose commit only changed the changelog, so v1.13.1 was never deployed to production; this release includes its changes ([9ca7008](https://github.com/kalx-berkeley/staff-app/commit/9ca7008))
- Fix every deploy warning that it couldn't delete leftover backend folders holding only Python caches. Those folders are now removed ([31bf2ad](https://github.com/kalx-berkeley/staff-app/commit/31bf2ad))

## [1.13.1] - 2026-11-11

### Changed

- Dim a show on the DJ shows page, and offer View instead of Give Away Passes, once the DJ has given away a pass pair for it this DJ shift, since they can't give away another ([0ef0580](https://github.com/kalx-berkeley/staff-app/commit/0ef0580))
- Warn a DJ before showing a show whose remaining pass pairs are all pre-assigned to other DJs, naming those DJs and their airdates, and offer to pick a different show ([0ef0580](https://github.com/kalx-berkeley/staff-app/commit/0ef0580))

### Fixed

- Fix late-starting scheduled production deploys restarting production during live DJ hours. A scheduled run that starts outside 3:05–5:50am Pacific now deploys nothing, and the release waits for the next night. Manual deploys still deploy right away ([ea2dd32](https://github.com/kalx-berkeley/staff-app/commit/ea2dd32))

## [1.13.0] - 2026-11-10

### Added

- Add KALX Staff Analytics at `/analytics/` for site admins and promotions admins. It shows pass giveaway, short link and site usage metrics for a chosen time window, with an explanation of each metric. It tracks signed-in active days, DJ studio and station office sessions, "I'm off the mic" page visits, spin match popups and `/go/` redirects, and rolls them up to daily counts after 13 months ([#18](https://github.com/kalx-berkeley/staff-app/pull/18))
- Let promotions enter on-air and staff winners by hand when creating or editing a show, under Advanced, for carrying winners over from a cancelled, postponed or moved show. These winners skip the venue's win frequency limit and the lottery, and no one is notified ([a37ac1d](https://github.com/kalx-berkeley/staff-app/commit/a37ac1d))
- Let the on-air DJ correct the name, phone and email of a pass pair winner they recorded, within 4 hours of the giveaway and before the show closes ([0b17b50](https://github.com/kalx-berkeley/staff-app/commit/0b17b50))
- Link to a band's homepage, Bandcamp, Discogs, lyrics, free streaming and SoundCloud pages from its popup, whichever MusicBrainz lists ([aeaae3b](https://github.com/kalx-berkeley/staff-app/commit/aeaae3b))

### Changed

- Show a success message instead of the "already given away" warning right after a DJ gives away a pass pair ([92e3f41](https://github.com/kalx-berkeley/staff-app/commit/92e3f41))

## [1.12.2] - 2026-11-07

### Added

- List an existing show's recorded on-air winners and staff claims on the legacy import page, each with a Release button. Releasing promotes alternates and sends emails as usual ([585893c](https://github.com/kalx-berkeley/staff-app/commit/585893c))

## [1.12.1] - 2026-11-07

### Added

- Let promotions staff enter staff pass alternates, in queue order and with any +1 guests, on the legacy import page, for new and existing shows. As in the app, staff must hold every staff pass first, with none held for a +1 guest. Imported alternates aren't emailed

## [1.12.0] - 2026-11-07

### Changed

- Deploy production releases at 4am Pacific instead of as soon as they're published, so production doesn't restart while live DJs are using the system. A manual workflow run can still deploy the newest release right away ([44b33ef](https://github.com/kalx-berkeley/staff-app/commit/44b33ef))
- Read department names from the Department Heads table, since the All departments table is gone. The existing departments are kept if no record has a usable name ([4dd2cbf](https://github.com/kalx-berkeley/staff-app/commit/4dd2cbf))

### Added

- Reload open tabs after a deploy, so a tab left open, like the one in the DJ studio, doesn't keep running old code against the new backend. A tab reloads on the next page change or after 10 idle minutes, or after an idle hour if something was typed on the page, and offers a Reload button until then ([0668cc4](https://github.com/kalx-berkeley/staff-app/commit/0668cc4))

### Fixed

- Fix a page that fails to render or load leaving a blank screen. It now shows an error with a Retry button, and a tab asking for page code that a deploy removed reloads itself ([0668cc4](https://github.com/kalx-berkeley/staff-app/commit/0668cc4))

## [1.11.0] - 2026-11-05

### Changed

- Replace Extra Staff Passes on the show form with a Staff Pass Adjustment, which raises or lowers a show's staff passes from the standard one per pass pair. A show can have no staff passes, which also blocks staff lottery entry ([b077e95](https://github.com/kalx-berkeley/staff-app/commit/b077e95))
- Send each person one email when a show closes, instead of a separate email for each outcome ([#13](https://github.com/kalx-berkeley/staff-app/pull/13))
- List a show's staff passes by claim time: staff claims oldest first, then guest holds, then available passes ([e495246](https://github.com/kalx-berkeley/staff-app/commit/e495246))
- Set lottery winners' claim times to when they entered, so a winner cut by a pass reduction rejoins the alternate list by entry time instead of behind every lottery loser ([e495246](https://github.com/kalx-berkeley/staff-app/commit/e495246))
- Count only the pass pairs a DJ can give away on the DJ shows page, and offer View Show instead of Give Away when every pair left is pre-assigned to another DJ ([2882ff7](https://github.com/kalx-berkeley/staff-app/commit/2882ff7))
- Stack list view row actions on phones on the DJ shows page, and scroll the table sideways instead of clipping its buttons ([0af699a](https://github.com/kalx-berkeley/staff-app/commit/0af699a))
- Name the signed-in user, or `not-logged-in` for guests, along with the IP address on backend log lines, so limit who can read the journal accordingly ([1741f33](https://github.com/kalx-berkeley/staff-app/commit/1741f33))
- Cache directory photos for a year, using URLs that change when the photo or its format does ([04cb8e9](https://github.com/kalx-berkeley/staff-app/commit/04cb8e9))

### Added

- Let staff put their +1 guest on the alternate list when claiming a pass, entering the lottery or joining the alternate list. Two new options choose whether the staff member still attends if their guest has no pass when the show closes. Waiting guests get freed passes behind staff alternates and are listed in their own section. Existing claims, entries and alternates keep the choice they already made ([#13](https://github.com/kalx-berkeley/staff-app/pull/13), [3331d1d](https://github.com/kalx-berkeley/staff-app/commit/3331d1d))
- Let staff add a guest after claiming a pass, and remove their guest while keeping their own pass ([#13](https://github.com/kalx-berkeley/staff-app/pull/13))
- Let venues and promoters hold the emails telling +1 hosts and alternates the outcome when a show closes, until a KALX promotions rep sends them from the show page. This gives a rep time to ask the venue for more passes, reopen and re-close the show before anyone is told. Held emails are dropped once the show date passes ([4b373c5](https://github.com/kalx-berkeley/staff-app/commit/4b373c5))
- Add Clothespin to the DJ shows page, which reserves one unclaimed pass pair for today under a current DJ or specialty show name, and Release Reservation for a pre-assigned pair ([0af699a](https://github.com/kalx-berkeley/staff-app/commit/0af699a))
- Show alternates' contact details and queue times to promotions staff, and list a closed show's alternates below its guest list ([b8559a1](https://github.com/kalx-berkeley/staff-app/commit/b8559a1), [98da000](https://github.com/kalx-berkeley/staff-app/commit/98da000))

### Fixed

- Fix deleting a show leaving its lottery entries in place with no notice to the entrants. They're now emailed and their entries removed ([f32afd3](https://github.com/kalx-berkeley/staff-app/commit/f32afd3))
- Fix a direct staff claim bumping the guest on whichever card was clicked, which could bump an earlier claimer's guest. It now always bumps the newest guest ([e495246](https://github.com/kalx-berkeley/staff-app/commit/e495246))
- Fix a restart auto-closing a show that a rep reopened after its planned close time ([4b373c5](https://github.com/kalx-berkeley/staff-app/commit/4b373c5))
- Fix validation errors from schema validators returning a 500 instead of a 422 ([b077e95](https://github.com/kalx-berkeley/staff-app/commit/b077e95))
- Fix DJs' My Giveaways missing pre-assigned pairs whose name differs only in case ([0af699a](https://github.com/kalx-berkeley/staff-app/commit/0af699a))

## [1.10.0] - 2026-11-01

### Changed

- Make a show belong to its own promoter's KALX promotions reps, or its venue's when it has no promoter. A venue's default promoter now only pre-fills new shows. My Shows, show emails and promotions contacts follow this rule, and a show with a promoter uses the promoter's guest list requirements ([267f093](https://github.com/kalx-berkeley/staff-app/commit/267f093))
- Call a staff member and their guest a pair of passes on guest lists, and stop the auto-close email listing the guest hold as a second pass ([267f093](https://github.com/kalx-berkeley/staff-app/commit/267f093))
- Explain on the show form that any genre can be typed, separated by commas ([267f093](https://github.com/kalx-berkeley/staff-app/commit/267f093))
- Explain the venue form's Win Frequency Limit in a tooltip ([a71570a](https://github.com/kalx-berkeley/staff-app/commit/a71570a))

### Added

- Let venues and promoters include only staff pass winners' email addresses in the guest list, without DJs asking on-air winners for one. Venues and promoters that required email addresses still collect them from all winners ([267f093](https://github.com/kalx-berkeley/staff-app/commit/267f093))

## [1.9.1] - 2026-10-23

### Fixed

- Fix `/go/` short links telling staff in the station office to sign in without letting them. The station office network now goes through the Google login for short links like the rest of the site; only DJ studio computers, which can't sign in, skip it and are told to open the link elsewhere. Apache's `staff.conf` and `staff.stage.conf` must be updated when this is deployed ([d185836](https://github.com/kalx-berkeley/staff-app/commit/d185836))
- Fix station office guests on pass giveaway pages having no way to sign in. Staff whose session ran out now get a "Staff? Sign in" link that signs them in and returns them to the page ([d185836](https://github.com/kalx-berkeley/staff-app/commit/d185836))
- Fix staff whose session expired in an open tab getting an error instead of being asked to sign in again, and the expired session being logged as a possible bypass of Apache ([d185836](https://github.com/kalx-berkeley/staff-app/commit/d185836))

## [1.9.0] - 2026-10-22

### Changed

- Let 🆕 (new, not yet Active) staff use the staff app with the same roles and access as Active staff. The Airtable sync now imports them too. Only Active staff can claim staff passes, enter the staff pass lottery, join the alternate list, be site admins or use the Sublist DJ actions. The directory marks 🆕 staff with a badge ([eff5d69](https://github.com/kalx-berkeley/staff-app/commit/eff5d69))
- Stop telling staff pass lottery and alternate winners that they and their guest are on the guest list before the show closes. The emails now explain that a guest pass is only held until then, and that another staff member can still take it ([a93ec43](https://github.com/kalx-berkeley/staff-app/commit/a93ec43))
- Require a Spinitron link for each specialty show, and let promotions staff and a show's owners retire specialty shows and make them current again ([9bc3352](https://github.com/kalx-berkeley/staff-app/commit/9bc3352))
- Call venue and promoter owners "KALX promotions reps" in the pass giveaway, so they aren't mistaken for the venue's owners ([c1a458f](https://github.com/kalx-berkeley/staff-app/commit/c1a458f))
- Warn about a venue address's state or zip code only when it's at the end of the address, so house numbers no longer trigger the warning ([0d8078d](https://github.com/kalx-berkeley/staff-app/commit/0d8078d))
- Turn off the KALX Staff Directory in production while it's under construction, with the new `DIRECTORY_ENABLED` setting (off by default; deploys turn it on in staging only). When off, its API, scheduled jobs and profile page aren't registered, and the sub-site and its KALX Staff Admin section are hidden ([775f659](https://github.com/kalx-berkeley/staff-app/commit/775f659))
- Refresh KALX Workforms from Airtable nightly instead of every 15 minutes ([3176ceb](https://github.com/kalx-berkeley/staff-app/commit/3176ceb))

### Added

- Let venues be movie theaters. Shows at a movie theater have a movie rating (G, PG, PG-13, R, NC-17 or Not Rated) instead of an age restriction, and movie theaters have a default movie rating ([ef0e965](https://github.com/kalx-berkeley/staff-app/commit/ef0e965))
- Let wheelchair accessibility be Unknown for shows and venues ([adf2a17](https://github.com/kalx-berkeley/staff-app/commit/adf2a17))
- Add an option for venues with a logo to show their name next to the logo on the DJ show and giveaway pages. It's off by default, so existing venues still show only their logo ([67757a8](https://github.com/kalx-berkeley/staff-app/commit/67757a8))
- Add a profile page to the KALX Staff Directory at `/directory/me`, which site admins can open for anyone. It shows more than the directory does, the Sublist DJ requirements with their evidence, and a year of workforms. It also has an edit form, where a DJ name can be added from a Spinitron DJ or playlist link. Only the person and Active Paid Staff can save changes, and saving stays off until the new `AIRTABLE_STAFF_EDIT_ENABLED` setting is turned on. Site admins also get read-only views of anyone's workforms and set DJ Quiz deadlines in KALX Staff Admin ([9bc3352](https://github.com/kalx-berkeley/staff-app/commit/9bc3352), [1c38d7b](https://github.com/kalx-berkeley/staff-app/commit/1c38d7b), [ac009cb](https://github.com/kalx-berkeley/staff-app/commit/ac009cb))
- Add a People tab for KALX Workforms department heads, which lists who reported hours in their department in N of the last M months (2 of 3 by default). Heads can add people to their department from it once `AIRTABLE_STAFF_EDIT_ENABLED` is on ([1890ece](https://github.com/kalx-berkeley/staff-app/commit/1890ece), [31db04e](https://github.com/kalx-berkeley/staff-app/commit/31db04e))
- Add a Work types tab where KALX Workforms department heads offer predefined types of work for their departments, and choose whether staff can also describe other work in their own words (the default) ([99637ce](https://github.com/kalx-berkeley/staff-app/commit/99637ce))

### Fixed

- Fix closing a show during its lottery window leaving every lottery entrant without a pass. Its lottery is now drawn first ([492892b](https://github.com/kalx-berkeley/staff-app/commit/492892b))
- Fix reopening a show with the lottery on returning an error, and publishing a show with the lottery on drawing it about 7 hours late ([46291e0](https://github.com/kalx-berkeley/staff-app/commit/46291e0))
- Fix emptying a show's on-air description or caller special instructions, or a venue's win frequency, keeping the old value ([5e56327](https://github.com/kalx-berkeley/staff-app/commit/5e56327))
- Keep the KALX Workforms review card on screen while the list scrolls, and make clear that department heads don't need to submit a workform ([1890ece](https://github.com/kalx-berkeley/staff-app/commit/1890ece))

## [1.8.0] - 2026-10-18

### Changed

- Turn off the KALX Workforms sub-site in production while it's under construction, with the new `WORKFORMS_ENABLED` setting (off by default; deploys turn it on in staging only). When off, its API, scheduled jobs and Airtable syncs aren't registered and the sub-site is hidden ([51bf3a1](https://github.com/kalx-berkeley/staff-app/commit/51bf3a1))
- Suggest switching Google accounts on the `/go/` link page shown to people who aren't active staff, like the rest of the site's access page ([ea78cfb](https://github.com/kalx-berkeley/staff-app/commit/ea78cfb))

## [1.7.0] - 2026-10-17

### Changed

- Move scheduled jobs, the audit log and staging impersonation out of the pass giveaway's Admin page into the new KALX Staff Admin sub-site at `/admin/`. Sub-sites register their own scheduled jobs, so the KALX Workforms jobs are listed there too, and the Directory and Workforms get a button to end an impersonation ([8b4e7ae](https://github.com/kalx-berkeley/staff-app/commit/8b4e7ae), [2e88cd2](https://github.com/kalx-berkeley/staff-app/commit/2e88cd2))
- Split admins into two groups, both checked against the real signed-in user rather than anyone they're impersonating. Site admins (department heads, Paid Staff and the emails in the new `SITE_ADMIN_EMAILS` setting, all Active) can use everything. Promotions admins (the Promotions department) can use the pass giveaway's Admin page, see scheduled jobs without running them, and see only the pass giveaway's audit log entries. Every audit log entry now records which area it belongs to ([79880b7](https://github.com/kalx-berkeley/staff-app/commit/79880b7))
- Default the audit log to the last 7 days ([f1eae25](https://github.com/kalx-berkeley/staff-app/commit/f1eae25))
- Rename "Pass Call Instructions" to "call-in instructions" on the venue and promoter forms, and correct the help text, which said DJs see them ([1a5ec07](https://github.com/kalx-berkeley/staff-app/commit/1a5ec07))
- Clarify the venue and promoter form fields for show sourcing, default pass pairs and guest list requirements, and add tooltips to the promoter form's instruction fields ([cac344b](https://github.com/kalx-berkeley/staff-app/commit/cac344b), [e7996f5](https://github.com/kalx-berkeley/staff-app/commit/e7996f5))
- Simplify the staff and DJ My Passes pages: hide passes for shows more than 3 days past, drop winners' names and phone numbers from Given Away, and list only published shows under Pre-assigned to You ([8ef21da](https://github.com/kalx-berkeley/staff-app/commit/8ef21da), [b87b346](https://github.com/kalx-berkeley/staff-app/commit/b87b346), [8baeedb](https://github.com/kalx-berkeley/staff-app/commit/8baeedb))
- Leave FREEFORM and OVERNIGHTS out of DJ name suggestions and autocompletes (configurable with `SPINITRON_NON_DJ_SHOW_TITLES`) ([8ef21da](https://github.com/kalx-berkeley/staff-app/commit/8ef21da))
- Show staff +1 guest holds as guest holds, not second claims, on the promotions show page ([8ef21da](https://github.com/kalx-berkeley/staff-app/commit/8ef21da))
- Open the new show's page after publishing it, and open the next pass pair with a blank pre-assign form after saving a suggestion ([8ef21da](https://github.com/kalx-berkeley/staff-app/commit/8ef21da))
- Show the Winner Phone tooltip only for venues with a win frequency limit ([8ef21da](https://github.com/kalx-berkeley/staff-app/commit/8ef21da))
- Limit the show close date picker to dates up to the show date ([f1eae25](https://github.com/kalx-berkeley/staff-app/commit/f1eae25))
- Put the cursor in the staff directory search box when the page opens ([c16ca5c](https://github.com/kalx-berkeley/staff-app/commit/c16ca5c))
- Compress JSON, web manifests, icons and fonts with Apache's mod_deflate. Apache's `staff.conf` and `staff.stage.conf` must be updated and `a2enmod deflate` run when this is deployed ([8ef21da](https://github.com/kalx-berkeley/staff-app/commit/8ef21da))

### Added

- Add the KALX Workforms sub-site at `/workforms/`, marked as under construction and not yet the official way to submit workforms. Staff build each month's workform from entries (hours, description and an optional date) per department and submit it to the Airtable workforms table; it shows whether the 6-hour monthly minimum is met, except in months a leave of absence overlaps. Department heads, from the Airtable "Department Heads" table, approve or deny each department's hours. Reminder and review emails, with per-user email settings, are sent only when `WORKFORMS_EMAILS_ENABLED` is set, which defaults to off ([1e9a35d](https://github.com/kalx-berkeley/staff-app/commit/1e9a35d), [1850c44](https://github.com/kalx-berkeley/staff-app/commit/1850c44), [58544d5](https://github.com/kalx-berkeley/staff-app/commit/58544d5))
- Add Short Links: site admins manage `/go/<slug>` links in KALX Staff Admin, and only active staff can follow them. Apache's `staff.conf` and `staff.stage.conf` must be updated when this is deployed, to proxy `/go/` to the backend ([0089a82](https://github.com/kalx-berkeley/staff-app/commit/0089a82))
- Let promotions add extra staff passes to a show, beyond the usual one per pass pair, under Advanced on the show form ([fa3ed68](https://github.com/kalx-berkeley/staff-app/commit/fa3ed68))
- Add a default on-air description and caller special instructions to venues, which a new show at that venue starts with. Changing the show's venue replaces the text only if it's empty or still the previous venue's default. The venue's on-air description gets the same value-neutral language check as the show form's ([8c83912](https://github.com/kalx-berkeley/staff-app/commit/8c83912))
- Add show sourcing instructions to venues and promoters: notes for promotions staff on how to find out which shows a venue or promoter will give passes for, and how many ([ad18335](https://github.com/kalx-berkeley/staff-app/commit/ad18335))
- Warn DJs on the show page when they've already given away a pair for that show this shift ([bfbee8f](https://github.com/kalx-berkeley/staff-app/commit/bfbee8f))
- Add an email link for promotions contacts on the staff show page ([8ef21da](https://github.com/kalx-berkeley/staff-app/commit/8ef21da))
- Add a Tag button for band selections made by touch or keyboard ([8ef21da](https://github.com/kalx-berkeley/staff-app/commit/8ef21da))
- Add staff name autocomplete to Legacy Import's claimant fields and to staging impersonation, and DJ name autocomplete and field tooltips to Legacy Import ([313e019](https://github.com/kalx-berkeley/staff-app/commit/313e019), [8ef21da](https://github.com/kalx-berkeley/staff-app/commit/8ef21da))
- Apply the value-neutral description check and the venue's winner email and guest name rules in Legacy Import ([8ef21da](https://github.com/kalx-berkeley/staff-app/commit/8ef21da))

### Fixed

- Fix emptying a venue's or promoter's call-in instructions keeping the old text ([ad18335](https://github.com/kalx-berkeley/staff-app/commit/ad18335))
- Fix every edit to a published auto-close show rescheduling its auto-close job; the job now changes only when the show's status or close settings do ([3f954cc](https://github.com/kalx-berkeley/staff-app/commit/3f954cc))
- Fix restarts re-running already-drawn lotteries and logging a "deadline already passed" warning for each ([24de2a5](https://github.com/kalx-berkeley/staff-app/commit/24de2a5))
- Widen the KALX Staff Admin page so the audit log's Details column fits ([2e88cd2](https://github.com/kalx-berkeley/staff-app/commit/2e88cd2))

## [1.6.1] - 2026-10-10

### Changed

- Remove contact details that DJ studio and station office guests (no Google login) don't need from pass giveaway responses: staff phones and emails, winner emails, and promotions, venue and specialty-show owner contacts for every guest, plus winner phones for station office guests outside winner search ([6d85e14](https://github.com/kalx-berkeley/staff-app/commit/6d85e14))
- Limit viewing promoters to promotions staff ([6d85e14](https://github.com/kalx-berkeley/staff-app/commit/6d85e14))

### Removed

- Remove the unauthenticated `/api/users/debug/headers` endpoint ([6d85e14](https://github.com/kalx-berkeley/staff-app/commit/6d85e14))

### Fixed

- Fix the Airtable staff sync storing record IDs as departments (and so revoking department-based roles) now that the "Department" column links to the "All departments" table. The IDs are looked up there, and if any can't be found, that person's departments are left as they were and an error is reported ([d36141f](https://github.com/kalx-berkeley/staff-app/commit/d36141f))

## [1.6.0] - 2026-10-05

### Changed

- Sync staff from the "Online Staff App Directory" Airtable table instead of "KALX Active Staff Directory" by default (`AIRTABLE_TABLE_NAME` still overrides it) ([266bca8](https://github.com/kalx-berkeley/staff-app/commit/266bca8))
- Import only Airtable records whose Status includes "Active"; the new table also lists people who aren't active yet ("🆕"), and anyone listed but no longer Active loses access as if they'd left the table. `backend/scripts/delete_inactive_staff.py` removes the staff rows an earlier sync created for them ([3fd0c71](https://github.com/kalx-berkeley/staff-app/commit/3fd0c71))
- Take staff names from Airtable's "First Name" and "Surname" columns and pronouns from "Pronouns", instead of parsing them out of "Name" (which is still used as-is when both name columns are blank) ([997c221](https://github.com/kalx-berkeley/staff-app/commit/997c221))
- Simplify the page shown to Google accounts without access: a short note for people who aren't KALX staff, and three steps for staff signed in with the wrong Google account, with a link to the sign-in guide ([6d20991](https://github.com/kalx-berkeley/staff-app/commit/6d20991))

### Added

- Add the KALX Staff Directory at `/directory/`, where active staff can look up other active staff's photo, name, pronouns, DJ name, email, phone, departments, status, and titles and roles. Search, department and status filters, and sorting are kept in the URL so a view can be shared, and each person has a shareable detail page at `/directory/<id>`, with a "My record" shortcut to your own. Each DJ name links to its own Spinitron profile, and department and status tags link to the directory filtered on that value ([ab785dc](https://github.com/kalx-berkeley/staff-app/commit/ab785dc), [0b457bd](https://github.com/kalx-berkeley/staff-app/commit/0b457bd), [ed0261f](https://github.com/kalx-berkeley/staff-app/commit/ed0261f))
- Sync each staff member's pronouns, titles and roles, photo, and Airtable record ID from Airtable; photos (including iPhone HEIC/HEIF photos) are downloaded and resized only when they change, and an email address changed in Airtable now updates the existing staff record instead of creating a new one ([ab785dc](https://github.com/kalx-berkeley/staff-app/commit/ab785dc), [275b5a9](https://github.com/kalx-berkeley/staff-app/commit/275b5a9))
- Sync each staff member's leave of absence from Airtable's "LOA start" and "LOA end" columns. Staff can't claim a staff pass, enter the staff pass lottery, or join the alternate list for a show their leave covers; lottery entries and alternates whose leave covers the show are skipped when passes are handed out. Pre-assigning a pass pair to a DJ for a date during their leave shows a warning, promotions sees an "On leave" label on claimed passes and genre suggestions, and the directory sets apart staff on leave and shows the dates in their detail panel ([997c221](https://github.com/kalx-berkeley/staff-app/commit/997c221))
- In the directory, show the first line of each person's titles and roles under their name. DJ names of staff who can't sub for DJ shifts (not a Sublist DJ, or on leave by their leave dates or an "On leave" status) are greyed out and unlinked in the table, and their detail panel says why. The detail panel of anyone with an "On leave" status shows their leave dates, even past ones, or says none are on record ([61262d4](https://github.com/kalx-berkeley/staff-app/commit/61262d4))

## [1.5.0] - 2026-09-29

### Changed

- Serve the whole staff site from the app so it can host more sub-sites than the Radio Pass Giveaway: the frontend is served from the site root, and the API moves from `/pass-giveaway/api/` to `/api/`. Apache's `staff.conf` and `staff.stage.conf` must be updated when this is deployed ([1055355](https://github.com/kalx-berkeley/staff-app/commit/1055355))
- Replace the static staff portal landing page with a home page at `/` that shows a card for each sub-site you can use; Google accounts without access see the access help page there ([1055355](https://github.com/kalx-berkeley/staff-app/commit/1055355))
- Rename the browser tab and installed web app from "Radio Pass Giveaway" to "KALX Staff" outside the pass giveaway pages ([1055355](https://github.com/kalx-berkeley/staff-app/commit/1055355))

### Added

- Add links to the KALX Staff Portal home page and the other sub-sites at the top of the pass giveaway navigation ([1055355](https://github.com/kalx-berkeley/staff-app/commit/1055355))

## [1.4.0] - 2026-09-29

### Changed

- Rename the app's infrastructure from "promotions-app" to "staff-app" now that it is the KALX Staff App rather than only the pass giveaway: systemd units `staff-app-backend-{production,staging}`, deploy paths `~/staff-app-{production,staging}`, and database `staff-app.db`. The deploy migrates the server automatically; the Apache `Alias` and `<Directory>` paths must be updated to match ([35a1a49](https://github.com/kalx-berkeley/staff-app/commit/35a1a49))
- Cut the newest guest holds and then the newest staff claims (instead of random ones) when a show's pass count is reduced, and move cut claimers to the top of the alternate list ([839b714](https://github.com/kalx-berkeley/staff-app/commit/839b714))
- Link to the show's page from the email sent when a staff pass is released because its +1 guest was bumped ([839b714](https://github.com/kalx-berkeley/staff-app/commit/839b714))
- Only let staff release their own staff pass: the Release button now appears only on your own claim, and the API rejects staff releasing someone else's (promotions staff can still release any claim) ([839b714](https://github.com/kalx-berkeley/staff-app/commit/839b714))
- Keep users signed in for up to 7 days and across browser restarts, instead of ending every session within 8 hours; a session still ends after 24 hours without use ([a4967a7](https://github.com/kalx-berkeley/staff-app/commit/a4967a7))
- Make the DJ giveaway page a read-only preview for promotions staff: recording a giveaway or attempt now requires the DJ studio network (or, in staging, an active Sublist DJ) ([11de9d6](https://github.com/kalx-berkeley/staff-app/commit/11de9d6))
- Open My Passes to all staff and promotions members, showing their claimed staff passes and pending lottery entries; Sublist DJs still also see their giveaway history ([169a1a8](https://github.com/kalx-berkeley/staff-app/commit/169a1a8))
- Restyle the Legacy Import page to use the app's shared form styles ([d23f5bf](https://github.com/kalx-berkeley/staff-app/commit/d23f5bf))
- Improve mobile layouts: stack page headers above their buttons, let button rows wrap, and keep button labels on one line; shorten "Create New …" buttons to "New …" and "View Details" to "View" ([2d28edf](https://github.com/kalx-berkeley/staff-app/commit/2d28edf))

### Added

- Add a staff-pass alternate list: once every staff pass is held by a staff member, staff can join an ordered alternate list (with the same +1 guest options as a claim), and freed passes are assigned to the next alternate automatically with an email notification ([839b714](https://github.com/kalx-berkeley/staff-app/commit/839b714))
- Queue staff lottery losers as alternates in the order they entered, and state their alternate position in the lottery result email ([839b714](https://github.com/kalx-berkeley/staff-app/commit/839b714))
- Show alternates under a show's staff pass claims, and on My Passes, in amber with an "Alternate #N" label; promotions staff can remove alternates, who are emailed ([839b714](https://github.com/kalx-berkeley/staff-app/commit/839b714))
- Email alternates when a show closes without them getting a pass, when a reopened show puts them back in line, and when a show is deleted ([839b714](https://github.com/kalx-berkeley/staff-app/commit/839b714))
- Email staff pass holders when a show is deleted ([839b714](https://github.com/kalx-berkeley/staff-app/commit/839b714))
- Email staff whose pass is removed by a pass-count reduction, with their new alternate position ([839b714](https://github.com/kalx-berkeley/staff-app/commit/839b714))
- Add an "Add to Existing Show" mode to Legacy Import that backfills on-air winners and staff claims onto a show already created in the app, publishing it if it was still a draft ([d23f5bf](https://github.com/kalx-berkeley/staff-app/commit/d23f5bf))
- Let active Sublist DJ staff use the DJ view in staging without being on the DJ studio or station office network ([daf7372](https://github.com/kalx-berkeley/staff-app/commit/daf7372))
- Add a "Hide already closed shows" option, on by default, to the auto-close schedule on the Admin page ([d56d24d](https://github.com/kalx-berkeley/staff-app/commit/d56d24d))

### Fixed

- Show claim and giveaway times in Pacific time on the staff show page, staff and DJ My Passes, and the staff lottery deadline, matching the promotions and DJ show pages instead of the viewer's browser timezone ([839b714](https://github.com/kalx-berkeley/staff-app/commit/839b714))
- Fix the "log out and switch accounts" link on the unauthorized page, which didn't end the session, and always show Google's account chooser on sign-in so a wrong account isn't silently reused ([e560518](https://github.com/kalx-berkeley/staff-app/commit/e560518))
- Stop browsers from showing a cached copy of a sign-in-protected page after logout ([e560518](https://github.com/kalx-berkeley/staff-app/commit/e560518))
- Only schedule auto-close jobs while a show is published, so draft shows no longer appear on the Admin page's auto-close schedule ([2b3b7cf](https://github.com/kalx-berkeley/staff-app/commit/2b3b7cf))

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

[1.13.3]: https://github.com/kalx-berkeley/staff-app/compare/v1.13.2...v1.13.3
[1.13.2]: https://github.com/kalx-berkeley/staff-app/compare/v1.13.1...v1.13.2
[1.13.1]: https://github.com/kalx-berkeley/staff-app/compare/v1.13.0...v1.13.1
[1.13.0]: https://github.com/kalx-berkeley/staff-app/compare/v1.12.2...v1.13.0
[1.12.2]: https://github.com/kalx-berkeley/staff-app/compare/v1.12.1...v1.12.2
[1.12.1]: https://github.com/kalx-berkeley/staff-app/compare/v1.12.0...v1.12.1
[1.12.0]: https://github.com/kalx-berkeley/staff-app/compare/v1.11.0...v1.12.0
[1.11.0]: https://github.com/kalx-berkeley/staff-app/compare/v1.10.0...v1.11.0
[1.10.0]: https://github.com/kalx-berkeley/staff-app/compare/v1.9.1...v1.10.0
[1.9.1]: https://github.com/kalx-berkeley/staff-app/compare/v1.9.0...v1.9.1
[1.9.0]: https://github.com/kalx-berkeley/staff-app/compare/v1.8.0...v1.9.0
[1.8.0]: https://github.com/kalx-berkeley/staff-app/compare/v1.7.0...v1.8.0
[1.7.0]: https://github.com/kalx-berkeley/staff-app/compare/v1.6.1...v1.7.0
[1.6.1]: https://github.com/kalx-berkeley/staff-app/compare/v1.6.0...v1.6.1
[1.6.0]: https://github.com/kalx-berkeley/staff-app/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/kalx-berkeley/staff-app/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/kalx-berkeley/staff-app/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/kalx-berkeley/staff-app/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/kalx-berkeley/staff-app/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/kalx-berkeley/staff-app/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/kalx-berkeley/staff-app/releases/tag/v1.0.0
