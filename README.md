# Promotions Pass Giveaway System

A web-based application for managing radio station pass giveaways, coordinating between music venues, radio DJs, promotions staff, and station staff members.

## Before Deploying

Update these values before deploying to production:

1. **`apache/sites/auth.conf`** and **`apache/sites/staff.conf`**
   - Fill in `YOUR_GOOGLE_CLIENT_ID`, `YOUR_GOOGLE_CLIENT_SECRET`
   - Fill in `YOUR_OIDC_CRYPTO_PASSPHRASE` (generate with `openssl rand -base64 32`)
   - The same three values must be set identically in **both** VirtualHost blocks

2. **`backend/.env`**
   - Set `DJ_STUDIO_NETWORK` to your actual DJ studio network CIDR
   - Set `CORS_ORIGINS` to your production domain
   - Configure Airtable credentials for user sync

3. **GitHub Secrets** — configured in repo settings for the deploy workflow

## Overview

The system provides three distinct user interfaces:

- **Promotions Staff View** (`/pass-giveaway/promotions`): Manage shows, venues, and pass allocation
- **DJ View** (`/pass-giveaway/dj`): Record pass winners and giveaway attempts during live broadcasts
- **Staff Member View** (`/pass-giveaway/staff`): Browse and claim staff passes to events

The app is mounted at `/pass-giveaway/` on the staff site, managed by the
[`apache/`](apache/) directory in this repo, which owns the Apache VirtualHost and landing page.

## Features

The core workflow — create a show, allocate pass pairs, give them away on-air or let staff
claim them — is only part of what the app does. Some of the more notable features, grouped by
area:

### Show & venue management

- **Artist tagging in event names.** In the show form, promotions staff select any substring of
  the event name (e.g. the band's name inside `"Foo Fighters w/ Death Cab for Cutie"`) and a
  MusicBrainz artist search panel pops up at the selection; picking a result — or pasting a
  MusicBrainz artist URL — tags that exact span with the artist's MusicBrainz ID, type, country,
  and genre tags (`frontend/src/components/shared/BandAnnotator.tsx`).
- **Enriched show names.** Anywhere a tagged event name is displayed, the tagged spans become
  clickable: a popup shows a live Wikipedia extract (via MusicBrainz → Wikidata → Wikipedia), the
  artist's genre tags (click one to filter the show list by that genre), and a MusicBrainz link
  (`frontend/src/components/shared/EnrichedShowName.tsx`). If a show has no genre set, the app
  falls back to looking up the artist's MusicBrainz tags automatically.
- **Full show lifecycle** — draft → published → closed — plus soft-delete/undelete for shows,
  venues, and promoters, recoverable from the admin panel.
- **Auto-close scheduling.** A show can be set to close itself automatically at a planned date and
  time; the app emails the venue's guest list at that moment without anyone having to close it by
  hand. Shows that go unclosed past their date get a daily nag email to the venue owners instead.
- **Venue logo upload** with server-side validation, resizing, and re-encoding.
- **Promoters** can own a venue by default or override per show, with their own contacts and
  notification recipients.
- **DJ pre-assignment blackout window** — a venue (or an individual show) can forbid DJs from
  reserving a pass pair within N days of the show's close date, to keep last-minute reservations
  from crowding out the giveaway.
- **Legacy paper-form import** — a self-contained, removable feature for backfilling historical
  shows (with already-decided winners and claimants) during the cutover from the old paper-based
  process.

### Content safety: non-value-neutral language detection

KALX is a non-commercial station, so on-air copy about a show can state facts but can't praise
the band, promote the show, or tell listeners to go. As promotions staff type the on-air
description, the app flags language that reads as promotional rather than neutral
(`backend/app/services/language_analysis_service.py`):

- A curated lexicon catches endorsement words ("legendary," "unforgettable"), comparative/
  superlative claims ("the best," "unrivaled"), calls to action ("don't miss," "grab your"),
  station hype ("we're thrilled"), and a hard rule that it's "passes," never "tickets."
- A VADER sentiment pass catches other positively-charged words the lexicon doesn't list, while
  filtering out band/venue names and ordinary giveaway vocabulary ("free," "winner," "support")
  so they aren't mistaken for opinions.
- All-caps "shouting" and excessive exclamation points are flagged too.
- Every finding is advisory — a suggestion staff can dismiss, never a hard validation error,
  since band names and genre vocabulary can trip the heuristics.

### Lottery system

Shows can allocate passes by lottery instead of first-come giveaway/claiming
(`backend/app/services/lottery_service.py`). Staff and DJs enter separately during a configurable
window after the show is published:

- Staff entrants can request to bring a guest, and can mark that they'll only attend *with* that
  guest — in which case, if no guest pass is available, their own pass is returned to the pool for
  someone else.
- DJs enter for a specific on-air shift/date (optionally through a recurring "specialty show"),
  and winners get their pass pair pre-assigned automatically.
- The draw runs itself the moment the window closes (or can be triggered manually from the admin
  panel), and every entrant gets one of eight distinct outcome emails explaining exactly what
  happened to them and their guest.

### Feature bin (new releases) matching

KALX's "feature bin" — recently added releases — lives in a public Google Sheet. The app syncs it
nightly and fuzzy-matches feature-bin artists against tagged show artists (or, failing that, the
event name itself) so a show gets a **★ Feature Bin** badge when a performer has a new release in
the library, complete with the release's dot-color status and a listen link
(`backend/app/services/feature_bin_service.py`).

### DJ on-air tools

- **On-air giveaways** with a one-pair-per-DJ-per-4-hours guard so a single shift can't sweep the
  pool.
- **Failed-attempt logging** — a DJ can note that they announced a show but got no callers, which
  shows up in the guest-list email to the venue.
- **DJ name autocomplete**, remembered locally and backed by the staff directory plus historical
  on-air winner records.
- **Spinitron on-air schedule sync** — the app polls Spinitron's schedule API every 6 hours (12-hour
  lookahead, also refreshed immediately on startup) and caches who's on air and when each show
  changes over. The DJ Name field auto-fills from this, flags a warning with a one-click fix when
  the entered name doesn't match who's actually scheduled, and auto-advances to the next DJ (with a
  notice) right when a show ends.
- **Winner phone-number lookup**, restricted to the station office network or promotions staff and
  rate-limited per IP, so whoever answers the phone can verify a caller's story and release their
  passes back to the pool if it checks out.

### Staff experience

- Self-service pass claiming with an optional guest, including "only attend with guest" logic and
  a notification email if another staff member's claim bumps a pending guest.
- Per-user notification preferences (email on/off), honored by every email the app sends.
- A staff view for specialty (recurring DJ) shows the staff member belongs to.

### Admin & operations

- **Job dashboards** for every scheduled task (Airtable sync, feature bin sync, stale
  pre-assignment cleanup, unclosed-show notifications) with manual "run now" buttons, plus
  dashboards of every pending auto-close and lottery job with live countdowns.
- **Audit log viewer**, paginated and filterable by event type, actor, and date range — every
  giveaway, release, upload, and email send is logged with full details.
- **User impersonation** (staging only) — a promotions staff member can act as another user, or
  simulate the DJ studio network or station office network, to test role-specific views without
  borrowing real credentials.
- **Test-data seeding** (staging only) for populating a staging environment with sample venues and
  shows.
- **In-app feedback / bug report tool** that captures the current page and logged-in user and
  emails it straight to the webmaster.

### Auth & integrations

- Three-tier role model (promotions / staff / DJ) computed from Airtable-sourced staff status and
  department, with two separate trusted-network bypasses (the DJ studio and the station office)
  so those locations don't need Google logins, backed by a defense-in-depth check that rejects any
  request Apache didn't actually authenticate.
- Nightly syncs from **Airtable** (staff directory), **Google Sheets** (feature bin), and on-demand
  lookups against **MusicBrainz**, **Wikipedia**, and **Spinitron** (on-air DJ personas).
- Dual-path email delivery (smtp2go or local SMTP relay) that never silently drops a message, with
  staging mail suppressed except to the webmaster so feedback still works during testing.

## Technology Stack

**Backend:**
- Python 3.11+ with FastAPI
- SQLAlchemy ORM with SQLite database
- Uvicorn ASGI server, managed by systemd user service

**Frontend:**
- React 18+ with TypeScript and Vite
- Deployed as static files served by Apache

**Authentication:**
- Apache `mod_auth_openidc` for Google OAuth2 (all users except DJ studio network)
- DJ studio network IPs authenticate by source IP — no Google login required from the studio

**Infrastructure:**
- Apache 2.4+ with SSL (serves frontend, reverse proxies API)
- GitHub Actions for CI/CD with Netbird VPN for deployment

## Local Development

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API docs: http://localhost:8420/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend: http://localhost:3000/pass-giveaway/

### Running Tests

```bash
# Backend
cd backend
TZ=America/Los_Angeles pytest --cov

# Frontend
cd frontend
npm test
```

## Deployment

Push to `main` → deploys to staging automatically.
Publish a GitHub release → deploys to production.

See `SETUP_GUIDE.md` for first-time server setup.

## Architecture

```
Client
  │
  ├─► auth.kalx.berkeley.edu (Apache, port 443)
  │     │  mod_auth_openidc: handles Google OAuth2 callback (/redirect_uri)
  │     │  OIDCCookieDomain .kalx.berkeley.edu: session cookie shared with staff site
  │     └── Redirects direct visits → staff.kalx.berkeley.edu
  │
  └─► staff.kalx.berkeley.edu (Apache, port 443)  [apache/ — this repo]
        │  mod_auth_openidc: validates shared session cookie; initiates login via auth site
        │  Sets X-Forwarded-User header from OIDC email claim
        │
        ├── /          →  landing page (apache/www/html/staff/)
        │
        └── /pass-giveaway/  [kalx-promotions — this project]
              │
              │  Authentication (Apache layer):
              │    DJ studio network IP  → authenticated without OIDC
              │    No OIDC session + non-DJ IP → redirect to Google login
              │    Valid OIDC session   → authenticated
              │
              │  Passes to backend:
              │    X-Forwarded-User: OIDC email (absent for DJ-network-only requests)
              │    X-Forwarded-For: real client IP (set by mod_proxy)
              │
              ├── Static files  →  /home/staff-app/promotions-app-production/frontend/dist/
              │                    (staging: /home/staff-app/promotions-app-staging/frontend/dist/)
              │
              └── /pass-giveaway/api/*  →  Uvicorn (127.0.0.1:8420, staff-app user)
                                              (staging: 127.0.0.1:8421)
                                              │  (Apache strips /pass-giveaway prefix)
                                              │  Defense-in-depth: 400 if neither
                                              │  X-Forwarded-User nor DJ network IP present
                                              └── SQLite database
```

**Authentication flow:**
1. Staff/promotions users: `staff.kalx.berkeley.edu` → mod_auth_openidc redirects to Google →
   callback at `auth.kalx.berkeley.edu/redirect_uri` → session cookie on `.kalx.berkeley.edu` →
   redirected back with session accepted.
2. DJ studio IPs: Apache marks request as `IS_DJ_NETWORK` and allows through without OIDC;
   backend verifies IP is in `DJ_STUDIO_NETWORK` via `X-Forwarded-For`.
3. Unauthenticated non-DJ IPs: always redirected to Google OIDC — no anonymous access.

## Configuration

### Backend Environment Variables

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | SQLite path | `sqlite:///./promotions.db` |
| `DJ_STUDIO_NETWORK` | DJ studio CIDR | `192.168.1.0/24` |
| `AIRTABLE_API_KEY` | Airtable API key | — |
| `AIRTABLE_BASE_ID` | Airtable base ID | — |
| `AIRTABLE_TABLE_NAME` | Staff directory table | `KALX Active Staff Directory` |
| `CORS_ORIGINS` | Allowed CORS origins | `http://localhost:3000` (production: `https://staff.kalx.berkeley.edu`) |
| `SMTP2GO_API_KEY` | smtp2go API key for email notifications | — (falls back to local SMTP relay when unset) |
| `EMAIL_FROM_ADDRESS` | From address for notification emails | `noreply@kalx.berkeley.edu` |
| `LOCAL_SMTP_HOST` | Hostname of the local SMTP relay used when `SMTP2GO_API_KEY` is unset | `localhost` |
| `LOCAL_SMTP_PORT` | Port of the local SMTP relay used when `SMTP2GO_API_KEY` is unset | `25` |
| `WEBMASTER_EMAIL` | Recipient for in-app feedback and bug reports | — |
| `FEATURE_BIN_SHEET_ID` | Google Sheet ID for the KALX feature bin (new-arrivals) list | — (feature bin sync is disabled if unset) |
| `FEATURE_BIN_SHEET_GID` | Worksheet `gid` of the sheet's "Current Active A-Z" tab | — (feature bin sync is disabled if unset) |

Note: CORS is same-origin in production (frontend and API are both on `staff.kalx.berkeley.edu`), so `CORS_ORIGINS` only matters for local development.

When `SMTP2GO_API_KEY` is set, emails are sent via smtp2go. When it is not set, emails are sent via the OS's local SMTP relay (`LOCAL_SMTP_HOST`/`LOCAL_SMTP_PORT`, e.g. `sendmail`/Postfix listening on `localhost:25`) instead of failing or silently dropping the message. Separately, when `ENVIRONMENT=staging`, emails are logged rather than sent regardless of which path would otherwise be used. The one exception is `WEBMASTER_EMAIL`: in staging, emails to the webmaster are always delivered so that feedback submitted via the in-app form reaches the webmaster even during testing.

### Airtable Schema

**Table: KALX Active Staff Directory**

| Field | Type |
|---|---|
| `Name` | multilineText |
| `Photo` | multipleAttachments |
| `Email address` | email |
| `Phone` | phoneNumber |
| `Titles and Roles` | richText |
| `DJ Name` | richText |
| `Department` | singleLineText |
| `Status` | multipleSelects |

### GitHub Actions Secrets/Variables

**Secrets:**
- `NETBIRD_SETUP_KEY`
- `SSH_PRIVATE_KEY` (deploy key for `staff-app` user)
- `AIRTABLE_API_KEY`
- `AIRTABLE_BASE_ID`
- `SMTP2GO_API_KEY` (optional — falls back to the server's local SMTP relay if absent)
- `FEATURE_BIN_SHEET_ID` (not public data — see the maintainers for the value; feature bin sync is disabled if unset)
- `FEATURE_BIN_SHEET_GID` (not public data — see the maintainers for the value; the sheet's "Current Active A-Z" tab)

**Variables:**
- `SITE_DOMAIN`
- `DJ_STUDIO_NETWORK`
- `NETBIRD_HOSTNAME` (the bare Netbird peer hostname, not the FQDN)
- `EMAIL_FROM_ADDRESS` (optional — defaults to `noreply@kalx.berkeley.edu`)
- `WEBMASTER_EMAIL` (optional — in-app feedback is disabled if unset; in staging, this is the only address that receives real email)

## Project Structure

```
.
├── apache/                     # Staff portal website: Apache VirtualHosts and landing pages
│   ├── sites/                  # auth/staff VirtualHost configs (production + staging)
│   ├── confs/                  # Shared variables and secrets, loaded via a2enconf
│   ├── www/html/               # Static landing pages (auth, auth.stage, staff, staff.stage)
│   └── README.md
├── backend/                    # Python FastAPI backend
│   ├── app/
│   ├── tests/
│   └── requirements.txt
├── frontend/                   # React TypeScript frontend (mounted at /pass-giveaway/)
│   ├── src/
│   └── package.json
├── systemd/                    # Systemd service files
│   ├── promotions-app-backend-production.service
│   └── promotions-app-backend-staging.service
├── docs/specs/                 # Architecture and requirements
└── .github/workflows/
    └── deploy.yml
```

## Maintenance

### Logs

```bash
# Backend (as staff-app user)
journalctl --user -u promotions-app-backend-production -f
journalctl --user -u promotions-app-backend-staging -f

# Apache (requires sudo)
sudo tail -f /var/log/apache2/kalx-auth-error.log
sudo tail -f /var/log/apache2/kalx-staff-error.log
```

### Restarting Services

```bash
# Backend (as staff-app user)
systemctl --user restart promotions-app-backend-production
systemctl --user restart promotions-app-backend-staging

# Apache (requires sudo)
sudo systemctl reload apache2
```

### Health Check

```bash
curl http://127.0.0.1:8420/health   # production
curl http://127.0.0.1:8421/health   # staging
```

### Database Migrations

```bash
cd ~/promotions-app-production/backend   # or ~/promotions-app-staging/backend
source venv/bin/activate
alembic upgrade head
```

Migrations run automatically on each deployment.

### Troubleshooting Authentication

Check that `mod_auth_openidc` is setting the header correctly:

```bash
curl -H "X-Forwarded-User: test@example.com" http://127.0.0.1:8420/api/users/me
```

Use the debug endpoint (from the server, bypassing Apache):

```bash
curl http://127.0.0.1:8420/api/users/debug/headers
```

