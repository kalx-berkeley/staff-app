A "Legacy Import" feature gated behind an environment variable LEGACY_IMPORT_ENABLED=true (defaults to false). When enabled, promotions staff get a new nav link and page to
enter historical show data from paper forms.

How to enable it

Set LEGACY_IMPORT_ENABLED=true in the backend's .env file (or environment), then restart the backend. The frontend detects this automatically and shows the "Legacy Import"
link in the promotions nav.

What the form does

- Accepts all standard show fields (event name, venue, date/time, description, age restriction, etc.)
- Shows N rows for on-air winners (one per pass pair) — name, phone, email, and DJ name
- Shows N dropdowns for staff claimants — pick which staff member claimed each staff pass
- Blank winner/claimant rows are skipped (partial entry is fine)
- Creates the show immediately in "closed" status — no notifications, no publish/close lifecycle
- After a successful import, the form resets so the next show can be entered without navigating away

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