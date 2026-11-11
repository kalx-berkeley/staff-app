A "Legacy Import" feature gated behind an environment variable LEGACY_IMPORT_ENABLED=true (defaults to false). When enabled, promotions staff get a new nav link and page to
enter historical show data from paper forms.

How to enable it

Set LEGACY_IMPORT_ENABLED=true in the backend's .env file (or environment), then restart the backend. The frontend detects this automatically and shows the "Legacy Import"
link in the promotions nav.

What the form does

It has two modes, toggled at the top of the page:

- **New Show** — accepts all standard show fields (event name, venue, date/time,
  description, age restriction, etc.), shows N rows for on-air winners (one per
  pass pair), N dropdowns for staff claimants and a list of alternates, in queue
  order. Blank winner/claimant rows are skipped (partial entry is fine), but
  alternates need every staff pass held by a staff member, as in the app.
  Creates the show immediately in "published"
  status — no notifications, no publish/close lifecycle. After a successful
  import, the form resets so the next show can be entered without navigating
  away.
- **Add to Existing Show** — for shows promotions staff already entered in
  staff-app (via the normal show form) before the paper-to-app cutover. Lets
  them search for that show and record on-air winners / staff claims against
  its existing passes, and add alternates to the end of its queue, instead of
  duplicating it. A draft show is published as
  part of the merge. It also lists the show's recorded on-air winners and staff
  claims, each with a Release button that calls the app's normal release
  endpoints, so the usual emails and alternate promotions happen.

How to remove it later

Delete these files:
- backend/app/pass_giveaway/routers/legacy_import.py
- backend/app/pass_giveaway/schemas/legacy_import.py
- frontend/src/pass-giveaway/promotions/LegacyImport.tsx

Then remove these small hooks in existing files:
- backend/app/config.py — the legacy_import_enabled line
- backend/app/main.py — the import and the if settings.legacy_import_enabled: block
- frontend/src/pass-giveaway/api.ts — the legacyImportAPI export and the Legacy* interfaces
- frontend/src/pass-giveaway/PassGiveawayApp.tsx — the LegacyImport lazySection and route
- frontend/src/pass-giveaway/promotions/index.ts — the LegacyImport export line
- frontend/src/pass-giveaway/promotions/PromotionsLayout.tsx — the legacyImportAPI import, the legacyImportEnabled state, and the nav <li>
- The server's `~/staff-app-production/backend/.env` and `~/staff-app-staging/backend/.env` - the `LEGACY_IMPORT_ENABLED` line, if there is one