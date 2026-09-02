# Complete Setup Guide

Setup and deployment guide for the Promotions Pass Giveaway System.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Google OAuth Setup](#google-oauth-setup)
3. [Server Setup](#server-setup)
4. [Apache Configuration](#apache-configuration)
5. [Backend Service Setup](#backend-service-setup)
6. [GitHub Actions Deployment Setup](#github-actions-deployment-setup)
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
- [ ] GitHub repository created with Actions enabled
- [ ] Netbird account (for secure deployments)
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
apt install -y ca-certificates curl gnupg apache2 python3.12 python3.12-venv python3-pip sqlite3 libjpeg-dev libapache2-mod-auth-openidc certbot python3-certbot-apache
# Install Netbird to enable deployments from GitHub Actions
wget -O /etc/apt/keyrings/netbird.asc https://pkgs.netbird.io/debian/public.key
echo 'deb [signed-by=/etc/apt/keyrings/netbird.asc] https://pkgs.netbird.io/debian stable main' | tee /etc/apt/sources.list.d/netbird.list
apt update
apt install netbird
netbird up --setup-key NETBIRD_SETUP_KEY

# Enable Apache modules needed for the app
a2enmod auth_openidc proxy proxy_http headers remoteip ssl rewrite
systemctl restart apache2
```

### 2. Create Application User

```bash
useradd --create-home --shell /bin/bash promotions

# Allow user services to run at boot
loginctl enable-linger promotions

# Create log directory
install --mode 0750 --owner promotions --group adm --directory /var/log/promotions

# Set up SSH access for deployments
mkdir -p /home/promotions/.ssh
chmod 700 /home/promotions/.ssh
touch /home/promotions/.ssh/authorized_keys
chmod 600 /home/promotions/.ssh/authorized_keys
chown --recursive promotions:promotions /home/promotions/.ssh

# Add deploy key (generated separately — see GitHub Actions setup)
cat deploy_key.pub >> /home/promotions/.ssh/authorized_keys
```

### 3. Create Application Directories

```bash
# As promotions user
sudo -u promotions bash << 'EOF'
mkdir -p /home/promotions/.config/systemd/user
mkdir -p /home/promotions/promotions-app/backend/data
mkdir -p /home/promotions/promotions-app/frontend/dist
EOF
chmod 755 /home/promotions
```

---

## Apache Configuration

The staff site Apache configuration lives in the `apache/` directory of this repo. The
`/pass-giveaway/` `Alias`, `Directory`, `Location`, and `ProxyPass` blocks for this app live
directly inside the staff VirtualHost config:

- **`apache/sites/auth.conf`** — `auth.kalx.berkeley.edu`: handles Google OAuth2 callbacks only
- **`apache/sites/staff.conf`** — `staff.kalx.berkeley.edu`: top-level staff site with landing page and all `/pass-giveaway/` location blocks inline

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

### 3. Deploy the Auth Site and Staff Landing Pages

The auth VirtualHost serves a small static page at `/` so that visitors who land there directly see something useful rather than a blank page or error. The staff VirtualHost serves a landing page linking to all available services.

```bash
mkdir -p /var/www/html/auth.kalx.berkeley.edu
mkdir -p /var/www/html/auth.stage.kalx.berkeley.edu
cp apache/www/html/auth/index.html /var/www/html/auth.kalx.berkeley.edu/
cp apache/www/html/auth.stage/index.html /var/www/html/auth.stage.kalx.berkeley.edu/

mkdir -p /var/www/html/staff.kalx.berkeley.edu
mkdir -p /var/www/html/staff.stage.kalx.berkeley.edu
cp apache/www/html/staff/index.html /var/www/html/staff.kalx.berkeley.edu/
cp apache/www/html/staff.stage/index.html /var/www/html/staff.stage.kalx.berkeley.edu/
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

The backend runs as a **user systemd service** under the `promotions` account — not a system service managed by root. A few things follow from this:

- All `systemctl` and `journalctl` commands must be run with `--user` **as the `promotions` user**. They will silently operate on the wrong service manager if run as root.
- `systemctl --user` requires a proper login session with `XDG_RUNTIME_DIR` set. It does **not** work inside a `sudo -u promotions bash` subshell, which lacks that environment variable. Always SSH into the server as the `promotions` user directly to run these commands.
- The service starts at boot because `loginctl enable-linger promotions` was run during server setup. Lingering keeps the user's systemd instance alive after logout; without it the backend would stop whenever no one is logged in.
- The service file sets `ProtectHome=read-only` for security hardening, but grants write access to `~/promotions-app/backend/data` via `ReadWritePaths`. That directory must exist before the service starts — it was created in Server Setup step 3.

### 1. Install the systemd Service

SSH into the server as the `promotions` user:

```bash
ssh promotions@your-server
```

Then copy the service file, enable it, and start it:

```bash
cp /path/to/repo/systemd/promotions-app-backend.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable promotions-app-backend.service
systemctl --user start promotions-app-backend.service
```

`enable` creates the symlink so the service starts at future boots. `start` starts it immediately — without this step the service will not run until the next reboot or re-login.

Verify it is running:

```bash
systemctl --user status promotions-app-backend
curl http://127.0.0.1:8000/health
```

### 2. Backend Environment

The `.env` file is **generated automatically by GitHub Actions** on every deployment from the configured GitHub secrets and variables — do not create it manually, as the workflow will overwrite it.

The workflow writes these variables into `~/promotions-app/backend/.env`:

| Variable | Source |
|---|---|
| `DATABASE_URL` | Hard-coded to the SQLite path under `~/promotions-app/backend/data/` |
| `DJ_STUDIO_NETWORK` | GitHub Actions variable `DJ_STUDIO_NETWORK` |
| `CORS_ORIGINS` | Derived from GitHub Actions variable `SITE_DOMAIN` |
| `AIRTABLE_API_KEY` | GitHub Actions secret `AIRTABLE_API_KEY` |
| `AIRTABLE_BASE_ID` | GitHub Actions secret `AIRTABLE_BASE_ID` |
| `SMTP2GO_API_KEY` | GitHub Actions secret `SMTP2GO_API_KEY` (optional) |
| `EMAIL_FROM_ADDRESS` | GitHub Actions variable `EMAIL_FROM_ADDRESS` (optional) |

Ensure all required values are configured in **Settings > Secrets and variables > Actions** before triggering the first deployment (see [GitHub Actions Deployment Setup](#github-actions-deployment-setup)).

If `SMTP2GO_API_KEY` is absent, the deployment will still succeed — email notifications will be sent via the server's local SMTP relay (`localhost:25` by default) instead of smtp2go until the key is added.

---

## GitHub Actions Deployment Setup

### 1. Generate Deploy Key

```bash
ssh-keygen -t ed25519 -C "kalx-promotions-deploy" -f deploy_key -N ""
```

- Add `deploy_key.pub` contents to `/home/promotions/.ssh/authorized_keys` on the server
- Add `deploy_key` (private key) as the `SSH_PRIVATE_KEY` GitHub secret

### 2. Configure GitHub Secrets

In **Settings > Secrets and variables > Actions**, create the following for each environment (staging, production):

**Secrets:**
- `NETBIRD_SETUP_KEY` — Netbird setup key for VPN access
- `SSH_PRIVATE_KEY` — private deploy key
- `AIRTABLE_API_KEY` — Airtable API key (optional)
- `AIRTABLE_BASE_ID` — Airtable base ID (optional)
- `SMTP2GO_API_KEY` — smtp2go API key for sending notification emails (optional; falls back to the server's local SMTP relay if absent)

**Variables:**
- `SITE_DOMAIN` — e.g., `staff.kalx.berkeley.edu` (the staff/app domain)
- `DJ_STUDIO_NETWORK` — CIDR of DJ studio network, e.g., `10.0.1.0/24`
- `NETBIRD_HOSTNAME` — Netbird peer name of the server
- `EMAIL_FROM_ADDRESS` — From address for notification emails (optional; defaults to `noreply@kalx.berkeley.edu`)

---

## First Deployment

All code deployment — backend and frontend — is handled by the GitHub Actions workflow defined in `.github/workflows/deploy.yml`. There is no manual code copy step.

### What the workflow does

On every push to `main` (staging) or published release (production) the workflow:

1. **Runs tests** — backend (`pytest`) and frontend (`tsc`, `eslint`, `npm test`)
2. **Builds the frontend** — `npm run build` produces `frontend/dist/`
3. **Connects to the server** via Netbird VPN using `NETBIRD_SETUP_KEY`
4. **Backs up the database** — copies `promotions.db` to a timestamped file before touching anything
5. **Rsyncs the backend** — copies `backend/` to `~/promotions-app/backend/` on the server, excluding `venv/` and cache files
6. **Rsyncs the frontend build** — copies `frontend/dist/` to `~/promotions-app/frontend/dist/`
7. **Writes `.env`** — generates `~/promotions-app/backend/.env` from GitHub secrets and variables (overwrites any previous file)
8. **Installs Python dependencies** — creates/updates `venv/` and runs `pip install -r requirements.txt`
9. **Runs database migrations** — `venv/bin/alembic upgrade head`
10. **Restarts the backend service** — `systemctl --user restart promotions-app-backend`
11. **Verifies** — polls until the backend responds on `http://127.0.0.1:8000/health`

### Prerequisites before first deployment

The workflow assumes the server is already set up (see [Server Setup](#server-setup) and [Apache Configuration](#apache-configuration)) and in particular:

- The `promotions` user exists and the deploy SSH key is in its `authorized_keys`
- The systemd service file is installed and **enabled** (step 1 of [Backend Service Setup](#backend-service-setup)); the workflow does `restart` not `start --now`, so `enable` must have been run first
- All GitHub Actions secrets and variables are configured

### Trigger

```
push to main        →  staging  environment
publish a release   →  production environment
```

To trigger manually: **Actions** tab → **Deploy** → **Run workflow**.

---

## Verification & Testing

### Check Services

```bash
# Backend service
systemctl --user status promotions-app-backend

# Apache
sudo systemctl status apache2

# Netbird (on server)
sudo netbird status
```

### Health Checks

```bash
# Backend health (from server, direct)
curl http://127.0.0.1:8000/health

# Via Apache (public)
curl https://staff.kalx.berkeley.edu/pass-giveaway/api/health
```

### Test Authentication

1. Open `https://staff.kalx.berkeley.edu` in a browser
2. You should be redirected to Google login (the callback goes through `auth.kalx.berkeley.edu`)
3. After login, you should be returned to `staff.kalx.berkeley.edu` and see the staff portal landing page
4. Click the "Radio Pass Giveaway" card — you should land at `https://staff.kalx.berkeley.edu/pass-giveaway/` and see the app
5. Open `https://staff.kalx.berkeley.edu/pass-giveaway/dj` — should load without requiring login (when accessed from DJ studio network) or prompt for Google login (from other networks)
6. Open `https://auth.kalx.berkeley.edu` in a browser — you should see the auth endpoint landing page with a link to the staff portal

---

## Deployment Operations

### Code Deployment (Backend + Frontend)

All code deployment is handled by GitHub Actions — there is no manual rsync or copy step for application code.

Push to `main` to deploy to staging, publish a GitHub release to deploy to production, or trigger the workflow manually from the Actions tab.

### Rollback

```bash
# Revert the commit on your local machine and push
git revert HEAD
git push origin main
```

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
(root-owned, in `/etc/apache2/sites-available/`) rather than in a file the `promotions` OS user
can write to. Changes to those blocks require manually copying the updated config and reloading
Apache — the GitHub Actions workflow does not deploy them.

---

## Common Operations

### Restart Backend

```bash
systemctl --user restart promotions-app-backend
```

### View Backend Logs

```bash
journalctl --user -u promotions-app-backend -f
journalctl --user -u promotions-app-backend -n 50
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
nano ~/promotions-app/backend/.env
systemctl --user restart promotions-app-backend
```

### Database Backup

```bash
cp ~/promotions-app/backend/data/promotions.db \
   ~/promotions-app/backend/data/backup_$(date +%Y%m%d_%H%M%S).db
```

### Sync Users from Airtable

Trigger via the admin UI (promotions staff only), or via the API:
```bash
curl -X POST https://staff.kalx.berkeley.edu/pass-giveaway/api/users/sync
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
ls ~/promotions-app/frontend/dist/index.html
```

If the file is missing, the frontend has not been built or deployed yet.

### 502 Bad Gateway

```bash
# Check backend is running
systemctl --user is-active promotions-app-backend
curl http://127.0.0.1:8000/health

# Check Apache config
sudo apache2ctl configtest
sudo tail -20 /var/log/apache2/kalx-staff-error.log
```

### Backend Won't Start

```bash
journalctl --user -u promotions-app-backend --no-pager -n 50

# Test manually
cd ~/promotions-app/backend
source venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Frontend Not Loading

```bash
ls -la ~/promotions-app/frontend/dist/
chmod 755 ~
chmod -R 755 ~/promotions-app/frontend/dist
```

### Deployment Failed

Check GitHub Actions logs in the browser. On the server:
```bash
sudo netbird status
ssh promotions@your-server   # Test SSH connectivity
df -h                         # Check disk space
```

---

## Complete Checklist

### One-Time Server Setup
- [ ] Installed Apache, mod_auth_openidc, Python, Netbird
- [ ] Created `promotions` user with lingering enabled
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
- [ ] Copied `promotions-app-backend.service` to `~/.config/systemd/user/` as the `promotions` user
- [ ] Ran `systemctl --user daemon-reload` and `systemctl --user enable promotions-app-backend` (via SSH as `promotions`, not via sudo)
- [ ] **Note:** do not manually create `.env` — the GitHub Actions workflow generates it from secrets/variables on first deployment

### GitHub Actions
- [ ] `SSH_PRIVATE_KEY` secret configured
- [ ] `NETBIRD_SETUP_KEY` secret configured
- [ ] `SITE_DOMAIN`, `DJ_STUDIO_NETWORK`, `NETBIRD_HOSTNAME` variables set
- [ ] Deploy key public key added to `promotions` user's `authorized_keys`

### First Deployment
- [ ] Pushed to `main` (staging) or published a release (production) to trigger GitHub Actions
- [ ] Workflow passed all tests, deployed code, ran migrations, and health-checked successfully
- [ ] App loads at `https://staff.kalx.berkeley.edu`
- [ ] Google login redirects correctly and returns to app
- [ ] DJ view accessible without login from DJ studio network
