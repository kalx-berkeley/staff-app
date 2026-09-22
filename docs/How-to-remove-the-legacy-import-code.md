A "Legacy Import" feature gated behind an environment variable LEGACY_IMPORT_ENABLED=true (defaults to false). When enabled, promotions staff get a new nav link and page to
enter historical show data from paper forms.

How to enable it

Set LEGACY_IMPORT_ENABLED=true in the backend's .env file (or environment), then restart the backend. The frontend detects this automatically and shows the "Legacy Import"
link in the promotions nav.

What the form does

It has two modes, toggled at the top of the page:

- **New Show** — accepts all standard show fields (event name, venue, date/time,
  description, age restriction, etc.), shows N rows for on-air winners (one per
  pass pair) and N dropdowns for staff claimants. Blank winner/claimant rows are
  skipped (partial entry is fine). Creates the show immediately in "published"
  status — no notifications, no publish/close lifecycle. After a successful
  import, the form resets so the next show can be entered without navigating
  away.
- **Add to Existing Show** — for shows promotions staff already entered in
  staff-app (via the normal show form) before the paper-to-app cutover. Lets
  them search for that show and record on-air winners / staff claims against
  its existing passes, instead of duplicating it. A draft show is published as
  part of the merge.

How to remove it later

Delete these files:
- backend/app/routers/legacy_import.py
- backend/app/schemas/legacy_import.py
- frontend/src/components/promotions/LegacyImport.tsx

Then remove these small hooks in existing files:
- backend/app/config.py — the legacy_import_enabled line
- backend/app/main.py — the import and the if settings.legacy_import_enabled: block
- frontend/src/services/api.ts — the legacyImportAPI export
- frontend/src/App.tsx — the LegacyImport import and route
- frontend/src/components/promotions/index.ts — the LegacyImport export line
- frontend/src/components/promotions/PromotionsLayout.tsx — the legacyImportAPI import, the legacyImportEnabled state, and the nav <li>
- .github/workflows/deploy.yml - LEGACY_IMPORT_ENABLED=${{ vars.LEGACY_IMPORT_ENABLED || 'false' }}