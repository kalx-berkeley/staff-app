# kalx-staff

Apache configuration for the KALX staff portal at `staff.kalx.berkeley.edu`.

The staff VirtualHost serves the staff-app frontend (this repo's `frontend/`) at `/`: a home
page linking to each sub-site, and the sub-sites themselves (such as the Radio Pass Giveaway at
`/pass-giveaway/`). It proxies `/api/` to the staff-app backend.

## Directory structure

```
apache/
  sites/
    auth.conf                        # Auth VirtualHost (production)
    auth.stage.conf                  # Auth VirtualHost (staging)
    staff.conf                       # Staff VirtualHost (production)
    staff.stage.conf                 # Staff VirtualHost (staging)
  www/
    html/
      auth/
        index.html                   # "Not intended for direct access" page
      auth.stage/
        index.html                   # Staging equivalent
```

`auth/index.html` and `auth.stage/index.html` link back to the staff portal by deriving
the hostname in JavaScript (swapping the `auth.` prefix for `staff.` on
`location.hostname`) rather than hardcoding a domain, so the same file works
unmodified regardless of domain suffix.

## Server setup

### Prerequisites

```bash
sudo apt install libapache2-mod-auth-openidc
sudo a2enmod auth_openidc proxy proxy_http headers remoteip ssl rewrite alias
```

### Deploy configs

```bash
# Copy Apache configs
sudo cp apache/sites/auth.conf        /etc/apache2/sites-available/
sudo cp apache/sites/staff.conf       /etc/apache2/sites-available/
sudo a2ensite auth.conf staff.conf

# Deploy the auth stub page
sudo mkdir -p /var/www/html/auth.kalx.berkeley.edu
sudo cp apache/www/html/auth/index.html /var/www/html/auth.kalx.berkeley.edu/
```

### Fill in credentials

Edit `/etc/apache2/sites-available/auth.conf` and
`/etc/apache2/sites-available/staff.conf`, replacing:

| Placeholder | Value |
|---|---|
| `YOUR_GOOGLE_CLIENT_ID` | From Google Cloud Console OAuth 2.0 credentials |
| `YOUR_GOOGLE_CLIENT_SECRET` | From Google Cloud Console OAuth 2.0 credentials |
| `YOUR_OIDC_CRYPTO_PASSPHRASE` | Random string — `openssl rand -base64 32` |

Both files must use **identical** values for all three placeholders so that the session cookie
established on `auth.kalx.berkeley.edu` is accepted by `staff.kalx.berkeley.edu`.

### SSL certificates

Obtain certificates via Certbot before enabling HTTPS:

```bash
sudo certbot certonly --apache -d auth.kalx.berkeley.edu
sudo certbot certonly --apache -d staff.kalx.berkeley.edu
```

### Reload Apache

```bash
sudo apachectl configtest && sudo systemctl reload apache2
```

## Adding a new sub-site

Sub-sites are added in the app, not here: register the sub-site in
`frontend/src/subsites.ts` and add its app to `SUBSITE_APPS` in `frontend/src/App.tsx`.
Every path is already served by the SPA and requires a Google login, so `staff.conf` only
needs to change if the new sub-site relaxes authentication for some of its paths, as the
Radio Pass Giveaway does for the DJ studio and station office networks.

Keeping all location blocks inside `staff.conf` (root-owned in `/etc/apache2/`) ensures
no application OS user can modify Apache configuration.

## Sub-sites

| Path | Sub-site |
|---|---|
| `/` | Home page linking to each sub-site |
| `/pass-giveaway/` | Radio Pass Giveaway |
