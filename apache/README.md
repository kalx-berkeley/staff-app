# kalx-staff

Apache configuration and landing page for the KALX staff portal at `staff.kalx.berkeley.edu`.

This project owns the staff website infrastructure. Individual applications (such as the Radio Pass
Giveaway) are separate projects that provide Apache Include snippets which this project references.

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
      staff/
        index.html                   # Staff portal landing page
      staff.stage/
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

# Deploy landing page and auth stub
sudo mkdir -p /var/www/html/auth.kalx.berkeley.edu
sudo cp apache/www/html/auth/index.html /var/www/html/auth.kalx.berkeley.edu/

sudo mkdir -p /var/www/html/staff.kalx.berkeley.edu
sudo cp apache/www/html/staff/index.html /var/www/html/staff.kalx.berkeley.edu/
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

## Adding a new service

1. Add the service's `Alias`, `Directory`, `Location`, and `ProxyPass` blocks directly to
   `apache/sites/staff.conf` (and the staging equivalent) under a new URL path.
2. Add a card to `apache/www/html/staff/index.html`.
3. Deploy the updated config and reload Apache.

Keeping all location blocks inside `staff.conf` (root-owned in `/etc/apache2/`) ensures
no application OS user can modify Apache configuration.

## Mounted applications

| Path | Project |
|---|---|
| `/pass-giveaway/` | [kalx-promotions](https://github.com/gene1wood/kalx-promotions) |
