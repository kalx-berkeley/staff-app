# KALX Staff App

- [KALX Staff App](#kalx-staff-app)
  * [Before Deploying](#before-deploying)
  * [Overview](#overview)
  * [Features](#features)
    + [Show & venue management](#show---venue-management)
    + [Content safety: non-value-neutral language detection](#content-safety--non-value-neutral-language-detection)
    + [Lottery system](#lottery-system)
    + [Feature bin (new releases) matching](#feature-bin--new-releases--matching)
    + [KALX Live! matching](#kalx-live--matching)
    + [DJ on-air tools](#dj-on-air-tools)
    + [Staff experience](#staff-experience)
    + [Admin & operations](#admin---operations)
    + [Auth & integrations](#auth---integrations)
  * [Technology Stack](#technology-stack)
  * [Local Development](#local-development)
    + [Backend](#backend)
    + [Frontend](#frontend)
    + [Running Tests](#running-tests)
  * [Deployment](#deployment)
    + [Deploying by hand](#deploying-by-hand)
    + [Checking on deploys](#checking-on-deploys)
    + [Deploy emails](#deploy-emails)
    + [When a deploy fails](#when-a-deploy-fails)
    + [Server settings](#server-settings)
    + [The GitHub token](#the-github-token)
  * [Architecture](#architecture)
  * [Configuration](#configuration)
    + [Backend Environment Variables](#backend-environment-variables)
    + [Airtable Schema](#airtable-schema)
  * [Project Structure](#project-structure)
  * [Maintenance](#maintenance)
    + [Logs](#logs)
    + [Restarting Services](#restarting-services)
    + [Health Check](#health-check)
    + [Database Migrations](#database-migrations)
    + [Troubleshooting Authentication](#troubleshooting-authentication)

The web application behind the KALX staff site. It hosts two sub-sites:

- **Radio Pass Giveaway** (`/pass-giveaway/`), for managing radio station pass giveaways,
  coordinating between music venues, radio DJs, promotions staff, and station staff members
- **KALX Staff Directory** (`/directory/`), where active staff look up each other's contact
  details (name, pronouns, photo, email, phone, DJ name, departments, status, and titles and
  roles) in a searchable, sortable, filterable table. The data comes from the same nightly
  Airtable sync that drives staff access, and is read-only here: changes are made in Airtable

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

3. **The server's deploy setup** — see [Deployment](#deployment) and `SETUP_GUIDE.md`

## Overview

The Radio Pass Giveaway sub-site provides three distinct user interfaces:

- **Promotions Staff View** (`/pass-giveaway/promotions`): Manage shows, venues, and pass allocation
- **DJ View** (`/pass-giveaway/dj`): Record pass winners and giveaway attempts during live broadcasts
- **Staff Member View** (`/pass-giveaway/staff`): Browse and claim staff passes to events

The app is mounted at `/pass-giveaway/` on the staff site, managed by the
[`apache/`](apache/) directory in this repo, which owns the Apache VirtualHost. The staff site's
home page at `/` is part of this app too: it links to each sub-site the signed-in user can use.

## Features

The core workflow — create a show, allocate pass pairs, give them away on-air or let staff
claim them — is only part of what the app does. Some of the more notable features, grouped by
area:

### Show & venue management

- **Artist tagging in event names.** In the show form, promotions staff select any substring of
  the event name (e.g. the band's name inside `"Foo Fighters w/ Death Cab for Cutie"`) and a
  MusicBrainz artist search panel pops up at the selection; picking a result — or pasting a
  MusicBrainz artist URL — tags that exact span with the artist's MusicBrainz ID, type, country,
  and genre tags (`frontend/src/pass-giveaway/components/BandAnnotator.tsx`).
- **Enriched show names.** Anywhere a tagged event name is displayed, the tagged spans become
  clickable: a popup shows a live Wikipedia extract (via MusicBrainz → Wikidata → Wikipedia), the
  artist's genre tags (click one to filter the show list by that genre), icons linking to the
  artist's homepage, Bandcamp, Discogs, lyrics, free streaming and SoundCloud pages (whichever
  MusicBrainz lists), and a MusicBrainz link
  (`frontend/src/pass-giveaway/components/EnrichedShowName.tsx`). If a show has no genre set, the app
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
- **Pre-assignment date restricted to the on-air schedule.** Both the staff self-reservation flow
  and promotions' "Pre-assign to DJ" box check the cached Spinitron schedule and restrict the date
  picker to dates the chosen DJ (or specialty show) is actually on air, with an override for
  exceptions and a warning when a picked date doesn't match.
- **"Suggest" a DJ for pre-assignment.** From the "Pre-assign to DJ" box on
  `/promotions/shows/:id`, suggest a DJ by on-air date (reversing the cached Spinitron schedule) or
  by genre (matching Sublist DJs and their specialty shows against the show's genres, from staff's
  own genre preferences). Accepting a suggestion with a known date auto-saves and advances to the
  next available pass pair.
- **Legacy paper-form import** — a self-contained, removable feature for backfilling historical
  shows (with already-decided winners and claimants) during the cutover from the old paper-based
  process.

### Content safety: non-value-neutral language detection

KALX is a non-commercial station, so on-air copy about a show can state facts but can't praise
the band, promote the show, or tell listeners to go. As promotions staff type the on-air
description, the app flags language that reads as promotional rather than neutral
(`backend/app/pass_giveaway/services/language_analysis_service.py`):

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
(`backend/app/pass_giveaway/services/lottery_service.py`). Staff and DJs enter separately during a configurable
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
(`backend/app/pass_giveaway/services/feature_bin_service.py`).

### KALX Live! matching

KALX Live! — the station's weekly in-studio live band performance — is scheduled on a public
Google Calendar. The app syncs it nightly as an ICS export and fuzzy-matches KALX Live! bands
against tagged show artists (or, failing that, the event name itself), so a show gets a
**🤘🏽 KALX Live!** badge when a performer recently was, or will be, on KALX Live! (within a
two-month lookback, with no limit on future dates), complete with the performance date(s)
(`backend/app/pass_giveaway/services/kalx_live_service.py`).

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
- **Live spin-match notifications** — polling `GET /api/dj/spin-matches` roughly every 30 seconds,
  the DJ view fuzzy-matches recently played Spinitron spins against shows with passes still to give
  away (`backend/app/pass_giveaway/services/spin_match_service.py`, reusing the feature bin's rapidfuzz approach)
  and pops up a dismissible toast with the artist, show, date, and a link straight to that show's
  giveaway page — so a DJ can catch a match and give tickets away in the next mic break. The
  Spinitron API itself is only re-polled once the cached spins are over a minute old, and a given
  spin is never surfaced more than once.
- **Winner phone-number lookup**, restricted to the station office network or promotions staff and
  rate-limited per IP, so whoever answers the phone can verify a caller's story and release their
  passes back to the pool if it checks out.

### Staff experience

- Self-service pass claiming with an optional guest, including "only attend with guest" logic and
  a notification email if another staff member's claim bumps a pending guest.
- Per-user notification preferences (email on/off), honored by every email the app sends.
- **Genre preferences** — staff can pick the genres they like from their profile, autocompleting
  from genres already in use on shows; used to power promotions' pre-assignment suggestions above.
- A staff view for specialty shows the staff member belongs to.

### Admin & operations

- **KALX Staff Admin** (`/admin/`) holds the admin tools shared by every staff site: the job
  dashboard, the audit log and user impersonation. Site admins (department heads, Paid Staff and
  anyone in `SITE_ADMIN_EMAILS`) can use all of it. Promotions admins (the Promotions department)
  can see the jobs without running them, and the pass giveaway's audit log entries. Both can use
  the pass giveaway's own admin page.
- **Job dashboard** for every scheduled task in every staff site (Airtable sync, feature bin sync,
  KALX Live! calendar sync, Spinitron on-air schedule sync, stale pre-assignment cleanup,
  unclosed-show notifications, workforms refresh and emails) with manual "run now" buttons. The
  pass giveaway's own admin page has dashboards of every pending auto-close and lottery job with
  live countdowns.
- **Audit log viewer**, paginated and filterable by event type, area, actor, and date range — every
  giveaway, release, upload, and email send is logged with full details.
- **User impersonation** (staging only) — an admin can act as another user, or
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
- Nightly syncs from **Airtable** (staff directory), **Google Sheets** (feature bin), a **Google
  Calendar** (KALX Live!), and on-demand lookups against **MusicBrainz**, **Wikipedia**, and
  **Spinitron** (on-air DJ personas).
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
- GitHub Actions for the tests; the server deploys itself with systemd timers

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

The server deploys both environments itself, and GitHub has no access to it.
A systemd service, `staff-app-deploy@<environment>`, fetches the code from
GitHub, builds the frontend, installs everything and restarts the backend.
Only what starts it differs:

| Environment | What it deploys | When |
|---|---|---|
| Staging | The newest commit on `main` | Within about 2 minutes of its tests passing (`staff-app-deploy-staging.timer` checks every 2 minutes) |
| Production | The newest release, the one GitHub marks "Latest" | 3:51am Pacific, while no live DJs are using the system (`staff-app-deploy-production.timer`) |

A commit is only deployed once its **Run Backend Tests** and **Run Frontend
Tests** checks have passed in GitHub Actions. To release, publish a GitHub
release: it goes live in production the next night.

The design, and the one-time server setup, are in
`docs/deployment/specs/server-side-deploy/plan.md`. The code is in `deploy/`
and the units are in `systemd/`.

### Deploying by hand

SSH into the server as `staff-app`, then:

```bash
# Deploy the newest release to production now, if it isn't live yet
systemctl --user start staff-app-deploy@production

# Redeploy the release that's already live
~/staff-app-deploy/production/fetch.py production --force

# Go back to an older release (the older release's code must work with the
# current database: migrations aren't undone)
~/staff-app-deploy/production/fetch.py production --ref v1.12.2 --force

# Redeploy staging's newest commit, for example after fixing a failed deploy
~/staff-app-deploy/staging/fetch.py staging --force

# Say what would be deployed, without changing anything
~/staff-app-deploy/production/fetch.py production --dry-run
```

Deploying by hand during live DJ hours restarts the backend for everyone on
the site. `systemctl --user start` waits until the deploy finishes and emails
if it fails, like the nightly run. Running `fetch.py` directly shows the
deploy's output on screen instead, and sends no failure email.

### Checking on deploys

```bash
systemctl --user list-timers 'staff-app-deploy-*'      # when each deploy runs next and last ran
journalctl --user -u staff-app-deploy@production       # production deploy logs
journalctl --user -u staff-app-deploy@staging          # staging deploy logs
cat ~/staff-app-production/DEPLOYED_VERSION            # what's live
```

Runs that find nothing to deploy log nothing, apart from systemd's own line
saying the service ran.

### Deploy emails

Deploy emails go to `WEBMASTER_EMAIL` (from that environment's `.env`) through
the server's local SMTP relay.

| Event | Email |
|---|---|
| A deploy fails (either environment) | Yes, with what happened and the end of the log |
| Production deploys a new release | Yes |
| The newest release's tests failed | Yes, each night until a newer release passes |
| The tests never ran for the newest release's commit | Yes, each night until a newer release passes |
| The release marked "Latest" is older than what's live | Yes |
| Production's nightly run can't reach GitHub | Yes |
| GitHub rejects the token | Yes, at most once a day |
| A staging commit's tests failed, or are still running | No (GitHub emails about failed runs) |
| The newest release's tests are still running at 3:51am | No (it deploys the next night) |
| Staging can't reach GitHub | No (it catches up on a later run) |

The same failure isn't emailed again within 12 hours.

### When a deploy fails

- **Production** rolls itself back: it restores the database backup taken just
  before the deploy and puts back the previous code. The failure email says
  whether that worked or production may be down. The nightly run tries the
  release again the next night.
- **Staging** is left as it is, for you to look at. It doesn't try that commit
  again until `main` has a newer commit, or you redeploy it with `--force`.

Every deploy backs up the database first, to
`backend/data/backup_<date>_<time>.db`.

### Server settings

Each environment's settings are in `~/staff-app-<environment>/backend/.env` on
the server, and are edited by hand. Deploys only ever change `APP_VERSION`.
After changing a setting, restart that backend, for example
`systemctl --user restart staff-app-backend-production`. When a release needs a
new setting, add it to production's `.env` before the release deploys.

### The GitHub token

The server uses a read-only GitHub token so GitHub doesn't throttle its checks.
It allows 5,000 API requests an hour instead of 60. When it expires, deploys
carry on without it, and an email says to replace it:

1. In GitHub, make a fine-grained personal access token with **Repository
   access: Public repositories (read-only)** and no permissions added. It can
   only read what anyone can see.
2. On the server, as `staff-app`, run
   `install -D -m 600 /dev/stdin ~/.config/staff-app-deploy/github-token`, paste
   the token, then press Enter and Ctrl-D.

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
        └── /  [staff-app — this project: one React SPA for the whole site]
              │
              │  /                →  home page linking to each sub-site
              │  /pass-giveaway/  →  Radio Pass Giveaway sub-site
              │  /directory/      →  KALX Staff Directory sub-site
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
              ├── Static files  →  /home/staff-app/staff-app-production/frontend/dist/
              │                    (staging: /home/staff-app/staff-app-staging/frontend/dist/)
              │
              └── /api/*  →  Uvicorn (127.0.0.1:8420, staff-app user)
                                (staging: 127.0.0.1:8421)
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
| `DATABASE_URL` | SQLite path | `sqlite:///./staff-app.db` |
| `DJ_STUDIO_NETWORK` | DJ studio CIDR | `192.168.1.0/24` |
| `AIRTABLE_API_KEY` | Airtable API key | — |
| `AIRTABLE_BASE_ID` | Airtable base ID | — |
| `AIRTABLE_TABLE_NAME` | Staff directory table | `Online Staff App Directory` |
| `STAFF_PHOTO_DIR` | Where the Airtable sync stores resized staff directory photos (relative to `backend/`) | `data/staff_photos` |
| `CORS_ORIGINS` | Allowed CORS origins | `http://localhost:3000` (production: `https://staff.kalx.berkeley.edu`) |
| `SMTP2GO_API_KEY` | smtp2go API key for email notifications | — (falls back to local SMTP relay when unset) |
| `EMAIL_FROM_ADDRESS` | From address for notification emails | `noreply@kalx.berkeley.edu` |
| `LOCAL_SMTP_HOST` | Hostname of the local SMTP relay used when `SMTP2GO_API_KEY` is unset | `localhost` |
| `LOCAL_SMTP_PORT` | Port of the local SMTP relay used when `SMTP2GO_API_KEY` is unset | `25` |
| `WEBMASTER_EMAIL` | Recipient for in-app feedback and bug reports | — |
| `APP_VERSION` | The deployed build, which open tabs compare with their own to know when to reload. Set by the deploy | — (tabs don't check when unset) |
| `SITE_ADMIN_EMAILS` | Comma-separated emails of extra site admins, besides department heads and Paid Staff (they must still be Active staff) | — |
| `FEATURE_BIN_SHEET_ID` | Google Sheet ID for the KALX feature bin (new-arrivals) list | — (feature bin sync is disabled if unset) |
| `FEATURE_BIN_SHEET_GID` | Worksheet `gid` of the sheet's "Currently Active Titles by Date" tab (only releases in the bin now) | — (feature bin sync is disabled if unset) |
| `KALX_LIVE_CALENDAR_ID` | Google Calendar ID for the KALX Live! performance schedule | — (KALX Live! sync is disabled if unset) |

Note: CORS is same-origin in production (frontend and API are both on `staff.kalx.berkeley.edu`), so `CORS_ORIGINS` only matters for local development.

When `SMTP2GO_API_KEY` is set, emails are sent via smtp2go. When it is not set, emails are sent via the OS's local SMTP relay (`LOCAL_SMTP_HOST`/`LOCAL_SMTP_PORT`, e.g. `sendmail`/Postfix listening on `localhost:25`) instead of failing or silently dropping the message. Separately, when `ENVIRONMENT=staging`, emails are logged rather than sent regardless of which path would otherwise be used. The one exception is `WEBMASTER_EMAIL`: in staging, emails to the webmaster are always delivered so that feedback submitted via the in-app form reaches the webmaster even during testing.

### Airtable Schema

**Table: Online Staff App Directory**

| Field | Type |
|---|---|
| `Name` | multilineText (used only when `First Name` and `Surname` are blank) |
| `First Name` | singleLineText |
| `Surname` | singleLineText |
| `Pronouns` | singleLineText |
| `Photo` | multipleAttachments |
| `Email address` | email |
| `Phone` | phoneNumber |
| `Titles and Roles` | richText |
| `DJ Name` | richText |
| `Department` | singleLineText |
| `Status` | multipleSelects (only records including `Active` are imported) |
| `LOA start` | date (first day of a leave of absence, inclusive) |
| `LOA end` | date (last day of a leave of absence, inclusive) |

## Project Structure

```
.
├── apache/                     # Staff portal website: Apache VirtualHosts and auth landing pages
│   ├── sites/                  # auth/staff VirtualHost configs (production + staging)
│   ├── confs/                  # Shared variables and secrets, loaded via a2enconf
│   ├── www/html/               # Static auth landing pages (auth, auth.stage)
│   └── README.md
├── backend/                    # Python FastAPI backend
│   ├── app/
│   │   ├── *.py                # Shared core: main, config, database, auth, scheduler
│   │   ├── models/             # All SQLAlchemy models (one shared database)
│   │   ├── common/             # Shared by every sub-site: users, Airtable sync, email
│   │   ├── pass_giveaway/      # Radio Pass Giveaway: routers/, services/, schemas/
│   │   └── directory/          # Staff Directory: routers/, schemas/
│   ├── tests/                  # common/, pass_giveaway/, directory/
│   └── requirements.txt
├── frontend/                   # React TypeScript SPA served at /
│   ├── src/
│   │   ├── App.tsx, subsites.ts  # App shell and the sub-site list
│   │   ├── common/             # Shared by every sub-site: API client, auth, utils
│   │   ├── home/               # Home page at /
│   │   ├── pass-giveaway/      # Radio Pass Giveaway at /pass-giveaway/
│   │   └── directory/          # Staff Directory at /directory/
│   └── package.json
├── deploy/                     # Server-side deploy scripts (fetch, install, notify) and their tests
├── systemd/                    # systemd units: the backends, and the deploy service and timers
├── docs/                       # Specs and how-tos, including deployment/
└── .github/workflows/
    └── tests.yml               # The tests, which every deployed commit must pass
```

## Maintenance

### Logs

```bash
# Backend (as staff-app user)
journalctl --user -u staff-app-backend-production -f
journalctl --user -u staff-app-backend-staging -f

# Apache (requires sudo)
sudo tail -f /var/log/apache2/kalx-auth-error.log
sudo tail -f /var/log/apache2/kalx-staff-error.log
```

### Restarting Services

```bash
# Backend (as staff-app user)
systemctl --user restart staff-app-backend-production
systemctl --user restart staff-app-backend-staging

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
cd ~/staff-app-production/backend   # or ~/staff-app-staging/backend
source venv/bin/activate
alembic upgrade head
```

Migrations run automatically on each deploy.

### Troubleshooting Authentication

Check that `mod_auth_openidc` is setting the header correctly:

```bash
curl -H "X-Forwarded-User: test@example.com" http://127.0.0.1:8420/api/users/me
```

