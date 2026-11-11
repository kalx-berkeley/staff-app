# Complete Setup Guide

Setup and deployment guide for the KALX Staff App.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Google OAuth Setup](#google-oauth-setup)
3. [Server Setup](#server-setup)
4. [Apache Configuration](#apache-configuration)
5. [Backend Service Setup](#backend-service-setup)
6. [Deploy Setup](#deploy-setup)
7. [First Deployment](#first-deployment)
8. [Verification & Testing](#verification--testing)
9. [Deployment Operations](#deployment-operations)
10. [Common Operations](#common-operations)
11. [Troubleshooting](#troubleshooting)
12. [Complete Checklist](#complete-checklist)

---

## Prerequisites

Before starting, ensure you have:

- [ ] Ubuntu 24.04 server with root access (or sudo rights to someone with root access)
- [ ] Domain name registered with DNS configured
- [ ] GitHub repository created with Actions enabled (Actions only runs the tests)
- [ ] A GitHub account to make the server's read-only token with
- [ ] Google Cloud account to create OAuth2 credentials
- [ ] Basic familiarity with Linux command line

---

## Google OAuth Setup

Authentication is handled entirely by Apache `mod_auth_openidc` using Google OAuth2. Users log in with their Google account; no separate auth service is needed.

### 1. Create Google OAuth2 Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project or select an existing one
3. Setup branding : https://console.cloud.google.com/auth/branding
   - App Information
     - App name : `KALX Staff`
     - User support email : Email address of a Google Group to be used for user support
   - Audience : `External`
   - Contact Information : The same Google Group as for user support
   - Finish : Click `I agree`
3. Go to **APIs & Services > Credentials > Create Credentials > OAuth Client ID** and click OAuth consent screen : https://console.cloud.google.com/apis/credentials/consent
   - Most items from having setup branding should be pre-filled
   - Go to "Branding"
     - Select a logo
     - App Domain : Application home page : A link to the KALX Staff site https://staff.kalx.berkeley.edu
     - App Domain : Application privacy policy link : A link to the KALX privacy policy https://oercs.berkeley.edu/policies/campus-policy-library/privacy-statement-uc-berkeley-websites
     - App Domain : Application terms of service link : A link to the KALX terms of service https://kalx.berkeley.edu/tos
     - Authorized Domains : Add domain : Add the domain name hosting the auth site. This is a second level domain (e.g. example.com) berkeley.edu
     - Click "Save"
5. Go to **APIs & Services > Credentials > Create Credentials > OAuth Client ID** : https://console.cloud.google.com/auth/clients/create
   - Application type: **Web application**
   - Name : KALX Staff
   - Authorized Javascript origins
     - https://staff.kalx.berkeley.edu
     - https://staff.stage.kalx.berkeley.edu
   - Authorized redirect URIs
     - https://auth.kalx.berkeley.edu/redirect_uri
     - https://auth.stage.kalx.berkeley.edu/redirect_uri
   - Click "Create"
6. Copy the **Client ID** and **Client Secret** and store them somewhere safe as this is your only chance to see the secret.

### 2. Generate OIDC Crypto Passphrase

```bash
openssl rand -base64 32
```

Save this value — you'll need it in the Apache config.

---

## Server Setup

These steps require root access and are typically done once by the server administrator.

### 1. Install Required Software

```bash
apt update
# libjpeg-dev is a requirement for the Pillow PyPi package
# Install mod_auth_openidc for Google OAuth
# git and rsync are used by the server's deploys (Node is installed by the deploys themselves)
apt install -y ca-certificates curl gnupg git rsync apache2 python3.12 python3.12-venv python3-pip sqlite3 libjpeg-dev libapache2-mod-auth-openidc certbot python3-certbot-apache

# Enable Apache modules needed for the app
a2enmod auth_openidc proxy proxy_http headers remoteip ssl rewrite
systemctl restart apache2
```

### 2. Create Application User

```bash
useradd --create-home --shell /bin/bash staff-app

# Allow user services to run at boot
loginctl enable-linger staff-app

# Create log directory
install --mode 0750 --owner staff-app --group adm --directory /var/log/staff-app

# Let administrators SSH in as staff-app, to run systemctl --user and manual deploys
mkdir -p /home/staff-app/.ssh
chmod 700 /home/staff-app/.ssh
touch /home/staff-app/.ssh/authorized_keys
chmod 600 /home/staff-app/.ssh/authorized_keys
chown --recursive staff-app:staff-app /home/staff-app/.ssh
cat your_key.pub >> /home/staff-app/.ssh/authorized_keys
```

### 3. Create Application Directories

Production and staging are fully separate deployments — separate directories, separate ports,
separate systemd services — so a staging deploy can never touch production code or data.

```bash
# As staff-app user
sudo -u staff-app bash << 'EOF'
mkdir -p /home/staff-app/.config/systemd/user
mkdir -p /home/staff-app/staff-app-production/backend/data
mkdir -p /home/staff-app/staff-app-production/frontend/dist
mkdir -p /home/staff-app/staff-app-staging/backend/data
mkdir -p /home/staff-app/staff-app-staging/frontend/dist
EOF
chmod 755 /home/staff-app
```

---

## Apache Configuration

The staff site Apache configuration lives in the `apache/` directory of this repo. The
`DocumentRoot`, `Directory`, `Location`, and `ProxyPass` blocks for this app live directly
inside the staff VirtualHost config:

- **`apache/sites/auth.conf`** — `auth.kalx.berkeley.edu`: handles Google OAuth2 callbacks only
- **`apache/sites/staff.conf`** — `staff.kalx.berkeley.edu`: top-level staff site; serves the app's frontend build at `/` and proxies `/api/` to the backend

mod_auth_openidc uses the shared passphrase to encrypt/decrypt session cookies, and `OIDCCookieDomain .kalx.berkeley.edu` scopes 
those cookies to all subdomains, so a user who logs in once on `auth.kalx.berkeley.edu` is recognized automatically on `staff.kalx.berkeley.edu`.

Variables and secrets are kept in two separate conf files loaded via `a2enconf`:

- **`apache/confs/kalx-variables.conf.example`** — non-secret values (`CLIENT_ID`, `DJ_STUDIO_NETWORK`).  World-readable permissions are acceptable.
- **`apache/confs/kalx-secrets.conf.example`** — secrets only (`CLIENT_SECRET`, `CRYPTO_PASSPHRASE`).  **Must be `chmod 640 root:root`** so that only root can read it.

### 1. Deploy the Apache VirtualHosts

Copy the VirtualHost configs from the repo:

```bash
cp apache/sites/auth.conf /etc/apache2/sites-available/auth.conf
cp apache/sites/staff.conf /etc/apache2/sites-available/staff.conf
cp apache/sites/auth.stage.conf /etc/apache2/sites-available/auth.stage.conf
cp apache/sites/staff.stage.conf /etc/apache2/sites-available/staff.stage.conf
```

### 1a. Deploy and configure the variables conf

```bash
cp apache/confs/kalx-variables.conf.example /etc/apache2/conf-available/kalx-variables.conf
nano /etc/apache2/conf-available/kalx-variables.conf
```

Fill in:
- `YOUR_GOOGLE_CLIENT_ID` — from Google Cloud Console
- `YOUR_DJ_STUDIO_NETWORK` — CIDR of the DJ studio network (e.g. `192.168.1.0/24`)

```bash
a2enconf kalx-variables
```

### 1b. Deploy and configure the secrets conf

```bash
cp apache/confs/kalx-secrets.conf.example /etc/apache2/conf-available/kalx-secrets.conf
chown root:root /etc/apache2/conf-available/kalx-secrets.conf
chmod 640 /etc/apache2/conf-available/kalx-secrets.conf
nano /etc/apache2/conf-available/kalx-secrets.conf
```

Fill in:
- `YOUR_GOOGLE_CLIENT_SECRET` — from Google Cloud Console
- `YOUR_OIDC_CRYPTO_PASSPHRASE` — generated with `openssl rand -base64 32`

Verify permissions before enabling:

```bash
stat -c '%a %U:%G %n' /etc/apache2/conf-available/kalx-secrets.conf
# Expected: 640 root:root ...
```

```bash
a2enconf kalx-secrets
```

The `OIDCRedirectURI` is already set to `https://auth.kalx.berkeley.edu/redirect_uri` in the VirtualHost configs and should not need changing.

### 2. Obtain SSL Certificates

Two certificates are needed, one per hostname:

```bash
certbot --apache -d auth.kalx.berkeley.edu
certbot --apache -d staff.kalx.berkeley.edu
certbot --apache -d auth.stage.kalx.berkeley.edu
certbot --apache -d staff.stage.kalx.berkeley.edu
```

### 3. Deploy the Auth Site Landing Pages

The auth VirtualHost serves a small static page at `/` so that visitors who land there directly see something useful rather than a blank page or error. The staff VirtualHost needs no static files of its own: its home page at `/` is part of the app, served from the deployed frontend build.

```bash
mkdir -p /var/www/html/auth.kalx.berkeley.edu
mkdir -p /var/www/html/auth.stage.kalx.berkeley.edu
cp apache/www/html/auth/index.html /var/www/html/auth.kalx.berkeley.edu/
cp apache/www/html/auth.stage/index.html /var/www/html/auth.stage.kalx.berkeley.edu/
```

### 4. Enable the Sites

```bash
a2ensite auth.conf staff.conf auth.stage.conf staff.stage.conf
apache2ctl configtest
systemctl reload apache2
```

### 5. Verify VirtualHost Routing

After enabling the sites, confirm that Apache is routing each hostname to the right VirtualHost and not to the default catch-all:

```bash
apache2ctl -S 2>&1 | grep -E 'auth\.|staff\.'
```

Each hostname should appear listed under port 443 pointing to your config file.  If a hostname is missing, the VirtualHost failed to load — check the main Apache error log for SSL certificate errors:

```bash
grep -i 'ssl\|certificate\|auth\.kalx' /var/log/apache2/error.log | tail -20
```

A common pitfall: Certbot sometimes sets the hostname it obtained a certificate for as the `ServerName` of the default SSL VirtualHost (`/etc/apache2/sites-enabled/000-default-le-ssl.conf`).  If that file has `ServerName auth.kalx.berkeley.edu`, all requests to the auth hostname will hit the default site instead of your VirtualHost.  Fix it by changing that `ServerName` back to the server's own hostname, then reload Apache.

### How Authentication Works

Apache `mod_auth_openidc` handles the entire OAuth2 flow:

1. A user visits `staff.kalx.berkeley.edu` with no session cookie.
2. mod_auth_openidc redirects them to Google for login, with the callback URL set to `https://auth.kalx.berkeley.edu/redirect_uri`.
3. After login, Google redirects to `auth.kalx.berkeley.edu/redirect_uri`.
4. mod_auth_openidc on the auth vhost exchanges the code for tokens, creates a session cookie scoped to `.kalx.berkeley.edu`, then redirects the user back to the original `staff.kalx.berkeley.edu` URL.
5. mod_auth_openidc on the staff vhost finds the session cookie and grants access.
6. Apache sets the `X-Forwarded-User` header to the user's Google email; the backend reads this header to identify the user.
7. DJ studio network IPs are authenticated by source IP at the Apache layer (`IS_DJ_NETWORK` env
   var). DJ-facing routes use `OIDCUnAuthAction pass` so these requests reach the backend without
   an OIDC session; the backend enforces IP-based authorization for DJ-specific endpoints.
   Unauthenticated non-DJ requests on DJ-accessible paths are redirected to `/pass-giveaway/`,
   which falls under the global OIDC-required block and initiates a Google login.
8. The backend performs a defense-in-depth check on every `/api/` request: if neither
   `X-Forwarded-User` nor a DJ studio network IP is present, the request is rejected with HTTP 400
   and a CRITICAL log entry is written — this indicates the Apache authentication layer was
   bypassed.

---

## Backend Service Setup

### How the Service Works

The backend runs as a **user systemd service** under the `staff-app` account — not a system service managed by root. A few things follow from this:

- All `systemctl` and `journalctl` commands must be run with `--user` **as the `staff-app` user**. They will silently operate on the wrong service manager if run as root.
- `systemctl --user` requires a proper login session with `XDG_RUNTIME_DIR` set. It does **not** work inside a `sudo -u staff-app bash` subshell, which lacks that environment variable. Always SSH into the server as the `staff-app` user directly to run these commands.
- The service starts at boot because `loginctl enable-linger staff-app` was run during server setup. Lingering keeps the user's systemd instance alive after logout; without it the backend would stop whenever no one is logged in.
- The service files set `ProtectHome=read-only` for security hardening, but grant write access to their respective `backend/data` directory via `ReadWritePaths`. Both directories must exist before the services start — they were created in Server Setup step 3.

There are two independent services — one per environment:

| | Production | Staging |
|---|---|---|
| Unit file | `staff-app-backend-production.service` | `staff-app-backend-staging.service` |
| Port | 8420 | 8421 |
| Working directory | `~/staff-app-production/backend` | `~/staff-app-staging/backend` |

### 1. Install the systemd Services

SSH into the server as the `staff-app` user:

```bash
ssh staff-app@your-server
```

Then copy both service files, enable them, and start them:

```bash
cp /path/to/repo/systemd/staff-app-backend-production.service ~/.config/systemd/user/
cp /path/to/repo/systemd/staff-app-backend-staging.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable staff-app-backend-production.service
systemctl --user enable staff-app-backend-staging.service
systemctl --user start staff-app-backend-production.service
systemctl --user start staff-app-backend-staging.service
```

`enable` creates the symlink so each service starts at future boots. `start` starts it immediately — without this step the service will not run until the next reboot or re-login.

Verify both are running:

```bash
systemctl --user status staff-app-backend-production
curl http://127.0.0.1:8420/health

systemctl --user status staff-app-backend-staging
curl http://127.0.0.1:8421/health
```

### 2. Backend Environment

Each environment's settings are in its own `backend/.env`
(`~/staff-app-production/backend/.env` and `~/staff-app-staging/backend/.env`),
which you write by hand and keep with mode 600. Deploys never overwrite it: they
only set its `APP_VERSION` line. After changing a setting, restart that backend.

```bash
install -m 600 /dev/null ~/staff-app-production/backend/.env
nano ~/staff-app-production/backend/.env
```

| Variable | Value |
|---|---|
| `DATABASE_URL` | `sqlite:////home/staff-app/staff-app-production/backend/data/staff-app.db` (or `-staging`) |
| `ENVIRONMENT` | `production` or `staging` |
| `FRONTEND_BASE_URL` | `https://staff.kalx.berkeley.edu` (or `https://staff.stage.kalx.berkeley.edu`) |
| `CORS_ORIGINS` | `https://kalx.berkeley.edu` |
| `DJ_STUDIO_NETWORK`, `STATION_OFFICE_NETWORK` | The networks' CIDRs |
| `AIRTABLE_API_KEY`, `AIRTABLE_BASE_ID` | Airtable credentials |
| `SPINITRON_API_KEY` | Spinitron API key (optional) |
| `WEBMASTER_EMAIL` | Gets in-app feedback, and the deploy emails |
| `EMAIL_FROM_ADDRESS` | Optional; defaults to `noreply@kalx.berkeley.edu` |
| `SMTP2GO_API_KEY` | Optional; without it, email goes through the local SMTP relay |
| `SITE_ADMIN_EMAILS` | Optional extra site admins, comma-separated |
| `WORKFORMS_ENABLED`, `DIRECTORY_ENABLED`, `LEGACY_IMPORT_ENABLED` | `true` or `false` |
| `FEATURE_BIN_SHEET_ID`, `FEATURE_BIN_SHEET_GID`, `KALX_LIVE_CALENDAR_ID` | Optional; see the maintainers for the values |
| `APP_VERSION` | Leave it out: deploys set it |

The README's "Backend Environment Variables" table lists every setting.

---

## Deploy Setup

The server deploys both environments itself, and GitHub has no access to it.
`staff-app-deploy@<environment>.service` fetches the code from GitHub, builds
the frontend, installs everything and restarts the backend. A timer starts it:
every 2 minutes for staging, and at 3:51am Pacific for production. See the
README's "Deployment" section for day-to-day use, and
`docs/deployment/specs/server-side-deploy/plan.md` for the design.

Do all of this SSHed in as `staff-app`.

### 1. Clone the repository

The deploys fetch code into this clone. The repository is public, so it needs
no credentials.

```bash
git clone https://github.com/kalx-berkeley/staff-app.git ~/staff-app-src
```

### 2. Save a GitHub token

In GitHub, make a fine-grained personal access token with **Repository access:
Public repositories (read-only)** and no permissions added. It only raises
GitHub's API limit from 60 to 5,000 requests an hour. Then save it:

```bash
install -D -m 600 /dev/stdin ~/.config/staff-app-deploy/github-token
# paste the token, press Enter, then Ctrl-D
```

### 3. Check what's live

Deploys skip a version that's already live, which they read from
`~/staff-app-<environment>/DEPLOYED_VERSION`. On a server the old GitHub
Actions deploy has deployed to, that file starts from the `APP_VERSION` in
`.env`, so check those values are right:

```bash
grep '^APP_VERSION=' ~/staff-app-production/backend/.env   # the release production has, e.g. v1.13.1
grep '^APP_VERSION=' ~/staff-app-staging/backend/.env      # the commit SHA staging has
```

If a line is missing, write the value yourself, for example
`echo v1.13.1 > ~/staff-app-production/DEPLOYED_VERSION`. On a brand-new
server, write the newest release for production and the newest commit on
`main` for staging, then deploy each once by hand with `--force` (see the
README).

### 4. Install the deploy scripts and units

```bash
cd ~/staff-app-src
for environment in staging production; do
  install -D -m 755 -t ~/staff-app-deploy/$environment deploy/fetch.py deploy/notify.py deploy/deploy_common.py
done
cp systemd/staff-app-deploy@.service systemd/staff-app-deploy-failed@.service \
   systemd/staff-app-deploy-production.timer systemd/staff-app-deploy-staging.timer \
   ~/.config/systemd/user/
systemd-analyze --user verify ~/.config/systemd/user/staff-app-deploy*
systemctl --user daemon-reload
```

From then on, deploys keep these up to date themselves.

### 5. Try it, then turn the timers on

```bash
~/staff-app-deploy/staging/fetch.py staging --dry-run
~/staff-app-deploy/production/fetch.py production --dry-run
systemctl --user enable --now staff-app-deploy-staging.timer staff-app-deploy-production.timer
systemctl --user list-timers 'staff-app-deploy-*'
```

### 6. Check lingering and email

```bash
loginctl show-user staff-app -p Linger   # must say Linger=yes, or the timers stop when you log out
python3 -c "import smtplib; smtplib.SMTP('localhost', 25).sendmail('noreply@kalx.berkeley.edu', ['YOU@example.com'], 'Subject: staff-app deploy email test\n\nIt works.')"
```

---

## First Deployment

Once the timers are on, staging deploys the newest commit on `main` within
about 2 minutes of its tests passing, and production deploys the newest release
at 3:51am Pacific. Each deploy:

1. **Checks** that the target isn't live yet and that its **Run Backend Tests**
   and **Run Frontend Tests** checks passed in GitHub Actions
2. **Fetches the code** with `git` into `~/staff-app-build/<environment>`
3. **Builds the frontend**, first installing or updating Node (the major
   version in `frontend/.node-version`) in `~/opt`
4. **Backs up the database** to `backend/data/backup_<date>_<time>.db`
5. **Copies the backend and frontend into place**, runs `pip install` and the
   migrations, and sets `APP_VERSION` in `.env`
6. **Installs the systemd units** and restarts the backend
7. **Verifies** that the backend answers `http://127.0.0.1:<port>/health`, then
   records the version in `DEPLOYED_VERSION`

Production and staging use different directories, ports and units, so they
never touch each other's code, database or running backend. If a production
deploy fails, it rolls back to what was live before.

---

## Verification & Testing

### Check Services

```bash
# Backend services
systemctl --user status staff-app-backend-production
systemctl --user status staff-app-backend-staging

# Deploy timers
systemctl --user list-timers 'staff-app-deploy-*'

# Apache
sudo systemctl status apache2
```

### Health Checks

```bash
# Backend health (from server, direct)
curl http://127.0.0.1:8420/health   # production
curl http://127.0.0.1:8421/health   # staging

# Via Apache (public)
curl https://staff.kalx.berkeley.edu/api/health
curl https://staff.stage.kalx.berkeley.edu/api/health
```

### Test Authentication

1. Open `https://staff.kalx.berkeley.edu` in a browser
2. You should be redirected to Google login (the callback goes through `auth.kalx.berkeley.edu`)
3. After login, you should be returned to `staff.kalx.berkeley.edu` and see the KALX Staff Portal home page
4. Click the "Radio Pass Giveaway" card — you should land at `https://staff.kalx.berkeley.edu/pass-giveaway/` and see the app
5. Open `https://staff.kalx.berkeley.edu/pass-giveaway/dj` — should load without requiring login (when accessed from DJ studio network) or prompt for Google login (from other networks)
6. Open `https://auth.kalx.berkeley.edu` in a browser — you should see the auth endpoint landing page with a link to the staff portal

---

## Deployment Operations

### Code Deployment (Backend + Frontend)

The server deploys code itself: staging from `main`, production from the newest
release. The README's "Deployment" section covers deploying by hand, going back
to an older release, logs and emails.

### Update Apache Config

After editing `apache/sites/auth.conf` or `apache/sites/staff.conf`:
```bash
sudo cp apache/sites/auth.conf /etc/apache2/sites-available/auth.conf
sudo cp apache/sites/staff.conf /etc/apache2/sites-available/staff.conf
sudo apache2ctl configtest
sudo systemctl reload apache2
```

Secrets and variables live in `/etc/apache2/conf-available/kalx-secrets.conf` and
`kalx-variables.conf` — they are never overwritten by a conf file update.

The `/pass-giveaway/` location blocks live directly inside `apache/sites/staff.conf`
(root-owned, in `/etc/apache2/sites-available/`) rather than in a file the `staff-app` OS user
can write to. Changes to those blocks require manually copying the updated config and reloading
Apache — deploys don't install Apache config.

---

## Common Operations

### Restart Backend

```bash
systemctl --user restart staff-app-backend-production
systemctl --user restart staff-app-backend-staging
```

### View Backend Logs

```bash
journalctl --user -u staff-app-backend-production -f
journalctl --user -u staff-app-backend-staging -f
journalctl --user -u staff-app-backend-production -n 50
```

### View Apache Logs

```bash
# Auth site (OAuth2 callbacks)
sudo tail -f /var/log/apache2/kalx-auth-error.log
sudo tail -f /var/log/apache2/kalx-auth-access.log

# Staff site (app, API proxy)
sudo tail -f /var/log/apache2/kalx-staff-error.log
sudo tail -f /var/log/apache2/kalx-staff-access.log
```

### Update Backend Environment

```bash
nano ~/staff-app-production/backend/.env   # or ~/staff-app-staging/backend/.env
systemctl --user restart staff-app-backend-production   # or -staging
```

### Database Backup

Every deploy backs up the database first. To make a backup by hand:

```bash
cp ~/staff-app-production/backend/data/staff-app.db \
   ~/staff-app-production/backend/data/backup_$(date +%Y%m%d_%H%M%S).db
```

### Sync Users from Airtable

Trigger via the admin UI (promotions staff only), or via the API:
```bash
curl -X POST https://staff.kalx.berkeley.edu/api/users/sync
```

---

## Troubleshooting

### Auth Site Shows the Default Apache Page

If visiting `https://auth.kalx.berkeley.edu` returns the default Ubuntu Apache welcome page rather than the landing page, the auth VirtualHost is not being matched.  Diagnose with:

```bash
apache2ctl -S 2>&1 | grep auth
```

The most common cause is that Certbot wrote `ServerName auth.kalx.berkeley.edu` into the default SSL VirtualHost (`/etc/apache2/sites-enabled/000-default-le-ssl.conf`) when it obtained the certificate. That file intercepts the hostname before your VirtualHost is consulted.  Fix: open that file, change `ServerName` back to the server's own hostname, then `systemctl reload apache2`.

A quick check that bypasses browser caching:
```bash
curl -sI https://auth.kalx.berkeley.edu/ | grep -E 'HTTP|Location|X-KALX'
```

### Redirect Loop After Authentication (Google → /redirect_uri → staff → Google …)

If the browser loops between the staff site, Google, and `/redirect_uri` after a seemingly successful Google login, the staff VirtualHost is not accepting the session cookie created by the auth VirtualHost.  Check the auth error log for decryption errors:

```bash
sudo grep -E 'decrypt|JWE|passphrase' /var/log/apache2/kalx-auth-error.log | tail -20
```

Causes and fixes:
- **`OIDCCryptoPassphrase` differs** between `auth.conf` and `staff.conf` — the auth site encrypts the session cookie with its passphrase and the staff site cannot decrypt it. Set the same value in both files and reload Apache.
- **`OIDCClientID` or `OIDCClientSecret` missing from the auth config** — the auth VirtualHost also needs all three OIDC values, not just the staff VirtualHost.
- **`OIDCSessionType client-cookie` missing** — without this directive, sessions are stored in the server's shared-memory cache which is not shared across VirtualHosts. Both `auth.conf` and `staff.conf` must include `OIDCSessionType client-cookie` so the session travels in the encrypted browser cookie instead.

### Authentication Not Working

Google OAuth issues appear in the Apache error logs:
```bash
# Auth site — problems with the OAuth callback
sudo tail -50 /var/log/apache2/kalx-auth-error.log

# Staff site — problems with session validation or access
sudo tail -50 /var/log/apache2/kalx-staff-error.log
```

Common causes:
- `OIDCClientID` or `OIDCClientSecret` wrong in Apache config, or different between the two VirtualHost blocks
- `OIDCCryptoPassphrase` differs between the two VirtualHost blocks (sessions won't be shared)
- Redirect URI `https://auth.kalx.berkeley.edu/redirect_uri` not registered in Google Cloud Console
- `mod_auth_openidc` not loaded: `apache2ctl -M | grep auth_openidc`

### 500 Error — Subrequest Nesting Limit Exceeded

If Apache logs `AH00125: Request exceeded the limit of 10 subrequest nesting levels`, the SPA fallback routing is creating an infinite internal redirect loop.  This can happen if `FallbackResource /index.html` is used together with `mod_auth_openidc` — the subrequest for `/index.html` re-enters the authentication handler, which can generate another subrequest, repeating until the limit is hit.

The staff configs use `mod_rewrite` with an explicit guard (`RewriteCond %{REQUEST_URI} !^/index\.html$`) to break the loop.  If you see this error, confirm the `<Directory>` block in `staff.conf` does not use `FallbackResource` and that `RewriteEngine On` is present with the three `RewriteCond` / `RewriteRule` lines.  Also verify that `index.html` actually exists in the frontend dist directory:

```bash
ls ~/staff-app-production/frontend/dist/index.html   # or ~/staff-app-staging/...
```

If the file is missing, the frontend has not been built or deployed yet.

### 502 Bad Gateway

```bash
# Check backend is running (production shown; swap -staging / 8421 as needed)
systemctl --user is-active staff-app-backend-production
curl http://127.0.0.1:8420/health

# Check Apache config
sudo apache2ctl configtest
sudo tail -20 /var/log/apache2/kalx-staff-error.log
```

### Backend Won't Start

```bash
journalctl --user -u staff-app-backend-production --no-pager -n 50   # or -staging

# Test manually
cd ~/staff-app-production/backend   # or ~/staff-app-staging/backend
source venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8420   # or 8421 for staging
```

### Frontend Not Loading

```bash
ls -la ~/staff-app-production/frontend/dist/   # or ~/staff-app-staging/...
chmod 755 ~
chmod -R 755 ~/staff-app-production/frontend/dist
```

### Deployment Failed

The failure email quotes the reason and the end of the log. On the server:

```bash
journalctl --user -u staff-app-deploy@production   # or @staging
systemctl --user list-timers 'staff-app-deploy-*'
df -h                                               # check disk space
```

---

## Complete Checklist

### One-Time Server Setup
- [ ] Installed Apache, mod_auth_openidc, Python, git and rsync
- [ ] Created `staff-app` user with lingering enabled
- [ ] Created application directories

### Google OAuth
- [ ] Created Google Cloud project and OAuth2 credentials
- [ ] Registered correct redirect URI (`https://auth.kalx.berkeley.edu/redirect_uri`)
- [ ] Generated OIDC crypto passphrase

### Apache Configuration
- [ ] Deployed `apache/sites/auth.conf` and `apache/sites/staff.conf` to `/etc/apache2/sites-available/`
- [ ] Deployed `kalx-variables.conf` from `apache/confs/kalx-variables.conf.example` with real values and enabled via `a2enconf kalx-variables`
- [ ] Deployed `kalx-secrets.conf` from `apache/confs/kalx-secrets.conf.example` with real secrets, `chmod 640 root:root`, and enabled via `a2enconf kalx-secrets`
- [ ] Obtained SSL certificate for `auth.kalx.berkeley.edu` via certbot
- [ ] Obtained SSL certificate for `staff.kalx.berkeley.edu` via certbot
- [ ] Verified `000-default-le-ssl.conf` (or equivalent) does not have `auth.kalx.berkeley.edu` or `staff.kalx.berkeley.edu` as its `ServerName`
- [ ] Deployed auth landing page: `sudo cp apache/www/html/auth/index.html /var/www/html/auth.kalx.berkeley.edu/`
- [ ] Enabled both sites with `a2ensite auth.conf staff.conf`
- [ ] Verified `apache2ctl configtest` passes
- [ ] Verified `apache2ctl -S` shows both hostnames routed to the correct config files (not the default VirtualHost)

### Backend
- [ ] Copied `staff-app-backend-production.service` and `staff-app-backend-staging.service` to `~/.config/systemd/user/` as the `staff-app` user
- [ ] Ran `systemctl --user daemon-reload` and `systemctl --user enable` for both services (via SSH as `staff-app`, not via sudo)
- [ ] Wrote each environment's `backend/.env` (mode 600)

### Deploys
- [ ] Cloned the repository to `~/staff-app-src`
- [ ] Saved the read-only GitHub token to `~/.config/staff-app-deploy/github-token` (mode 600)
- [ ] Checked or wrote each environment's `DEPLOYED_VERSION`
- [ ] Installed the deploy scripts and units, and `systemd-analyze --user verify` passes
- [ ] Turned on both deploy timers
- [ ] Lingering is on, and a test email through the local relay arrived

### First Deployment
- [ ] Pushed to `main`: staging deployed it once the tests passed
- [ ] Published a release: production deployed it at 3:51am, and the "deployed" email arrived
- [ ] App loads at `https://staff.kalx.berkeley.edu`
- [ ] Google login redirects correctly and returns to app
- [ ] DJ view accessible without login from DJ studio network
