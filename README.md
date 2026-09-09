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

API docs: http://localhost:8000/docs

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
              ├── Static files  →  /home/staff-app/promotions-app/frontend/dist/
              │
              └── /pass-giveaway/api/*  →  Uvicorn (127.0.0.1:8000, staff-app user)
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
│   └── promotions-app-backend.service
├── docs/specs/                 # Architecture and requirements
└── .github/workflows/
    └── deploy.yml
```

## Maintenance

### Logs

```bash
# Backend (as staff-app user)
journalctl --user -u promotions-app-backend -f

# Apache (requires sudo)
sudo tail -f /var/log/apache2/kalx-auth-error.log
sudo tail -f /var/log/apache2/kalx-staff-error.log
```

### Restarting Services

```bash
# Backend (as staff-app user)
systemctl --user restart promotions-app-backend

# Apache (requires sudo)
sudo systemctl reload apache2
```

### Health Check

```bash
curl http://127.0.0.1:8000/health
```

### Database Migrations

```bash
cd ~/promotions-app/backend
source venv/bin/activate
alembic upgrade head
```

Migrations run automatically on each deployment.

### Troubleshooting Authentication

Check that `mod_auth_openidc` is setting the header correctly:

```bash
curl -H "X-Forwarded-User: test@example.com" http://127.0.0.1:8000/api/users/me
```

Use the debug endpoint (from the server, bypassing Apache):

```bash
curl http://127.0.0.1:8000/api/users/debug/headers
```

