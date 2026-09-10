# Troubleshooting Quick Reference

Quick commands for common issues. For detailed troubleshooting, see [SETUP_GUIDE.md](SETUP_GUIDE.md).

Production and staging are independent deployments on the same server. Most commands below take
an environment-specific service name, port, and deploy path — set these once per shell session
and reuse them:

```bash
# Production
SERVICE=promotions-app-backend-production
PORT=8420
DEPLOY_PATH=~/promotions-app-production

# Staging
SERVICE=promotions-app-backend-staging
PORT=8421
DEPLOY_PATH=~/promotions-app-staging
```

## Quick Diagnostics

```bash
# Check all services
systemctl --user status $SERVICE

# Test backend locally
curl http://127.0.0.1:$PORT/health

# Test via Apache
curl https://staff.kalx.berkeley.edu/pass-giveaway/api/health          # production
curl https://staff.stage.kalx.berkeley.edu/pass-giveaway/api/health    # staging

# View recent logs
journalctl --user -u $SERVICE -n 50
```

## Common Issues

### Service Won't Start

```bash
# View detailed logs
journalctl --user -u $SERVICE --no-pager -n 100

# Check for port conflicts
ss -tlnp | grep $PORT

# Restart service
systemctl --user restart $SERVICE
```

### 502 Bad Gateway

```bash
# Check if backend is running
systemctl --user is-active $SERVICE
curl http://127.0.0.1:$PORT/health

# Check Apache config
sudo apache2ctl configtest

# View Apache errors (staff site handles /api/ proxying)
sudo tail -50 /var/log/apache2/kalx-staff-error.log
```

### Frontend Not Loading

```bash
# Check if files exist
ls -la $DEPLOY_PATH/frontend/dist/

# Fix permissions
chmod 755 ~
chmod 755 $DEPLOY_PATH
chmod 755 $DEPLOY_PATH/frontend
chmod -R 755 $DEPLOY_PATH/frontend/dist

# Check Apache logs
sudo tail -50 /var/log/apache2/kalx-staff-error.log
```

### Authentication Not Working

Google OAuth is handled by two Apache VirtualHosts using `mod_auth_openidc`:
- `auth.kalx.berkeley.edu` / `auth.stage.kalx.berkeley.edu` — handles the OAuth2 callback from Google
- `staff.kalx.berkeley.edu` / `staff.stage.kalx.berkeley.edu` — enforces authentication for the app

Check Apache logs on both sites:

```bash
# Auth site (OAuth callback issues)
sudo tail -50 /var/log/apache2/kalx-auth-error.log

# Staff site (session/access issues)
sudo tail -50 /var/log/apache2/kalx-staff-error.log

# Check mod_auth_openidc is loaded
apache2ctl -M | grep auth_openidc

# Test Apache config
sudo apache2ctl configtest

# Reload Apache
sudo systemctl reload apache2
```

Common causes:
- `OIDCClientID` or `OIDCClientSecret` incorrect — must be identical in **both** VirtualHost blocks for a given environment
- `OIDCCryptoPassphrase` differs between the two VirtualHost blocks — must be identical for session sharing to work
- Redirect URI (`https://auth.kalx.berkeley.edu/redirect_uri` or the `.stage.` equivalent) not registered in Google Cloud Console
- `OIDCCookieDomain` not set to `.kalx.berkeley.edu` (or `.stage.kalx.berkeley.edu`) in both VirtualHost blocks

### Deployment Failed

```bash
# Check GitHub Actions logs (in browser)
# Repository → Actions → View failed workflow

# On server, check Netbird
sudo netbird status

# Test SSH
ssh staff-app@your-server

# Check disk space
df -h
```

### Database Issues

```bash
# Check database file
ls -la $DEPLOY_PATH/backend/data/promotions.db

# Backup database
cp $DEPLOY_PATH/backend/data/promotions.db \
   $DEPLOY_PATH/backend/data/backup_$(date +%Y%m%d_%H%M%S).db

# Restart backend
systemctl --user restart $SERVICE
```

## Service Management

```bash
# Start service
systemctl --user start $SERVICE

# Stop service
systemctl --user stop $SERVICE

# Restart service
systemctl --user restart $SERVICE

# View status
systemctl --user status $SERVICE

# Enable/disable auto-start
systemctl --user enable $SERVICE
systemctl --user disable $SERVICE
```

## Log Management

```bash
# Follow logs in real-time
journalctl --user -u $SERVICE -f

# Last N lines
journalctl --user -u $SERVICE -n 100

# Since specific time
journalctl --user -u $SERVICE --since "2024-01-15 10:00:00"

# Between times
journalctl --user -u $SERVICE --since "10:00" --until "11:00"

# Search logs
journalctl --user -u $SERVICE | grep -i error

# Apache logs — auth site (OAuth2 callback), shared error/access log for both environments
sudo tail -f /var/log/apache2/kalx-auth-access.log
sudo tail -f /var/log/apache2/kalx-auth-error.log
sudo tail -f /var/log/apache2/kalx-stage-auth-access.log
sudo tail -f /var/log/apache2/kalx-stage-auth-error.log

# Apache logs — staff site (app, API proxy)
sudo tail -f /var/log/apache2/kalx-staff-access.log
sudo tail -f /var/log/apache2/kalx-staff-error.log
sudo tail -f /var/log/apache2/kalx-stage-staff-access.log
sudo tail -f /var/log/apache2/kalx-stage-staff-error.log
```

## Database Operations

```bash
# Backup database
cp $DEPLOY_PATH/backend/data/promotions.db \
   $DEPLOY_PATH/backend/data/backup_$(date +%Y%m%d).db

# Restore database
systemctl --user stop $SERVICE
cp $DEPLOY_PATH/backend/data/backup_YYYYMMDD.db \
   $DEPLOY_PATH/backend/data/promotions.db
systemctl --user start $SERVICE

# Check database integrity
cd $DEPLOY_PATH/backend
source venv/bin/activate
python3 << EOF
import sqlite3
conn = sqlite3.connect('data/promotions.db')
cursor = conn.cursor()
cursor.execute('PRAGMA integrity_check;')
print(cursor.fetchone())
conn.close()
EOF
```

## Configuration Changes

```bash
# Edit backend environment
nano $DEPLOY_PATH/backend/.env
systemctl --user restart $SERVICE

# Edit Apache config (requires root/sudo)
# Both auth and staff VirtualHosts for an environment are in the same file.
# Remember: OIDCClientID, OIDCClientSecret, and OIDCCryptoPassphrase
# must be identical in both VirtualHost blocks for that environment.
sudo nano /etc/apache2/sites-available/auth.conf          # production
sudo nano /etc/apache2/sites-available/staff.conf          # production
sudo nano /etc/apache2/sites-available/auth.stage.conf     # staging
sudo nano /etc/apache2/sites-available/staff.stage.conf     # staging
sudo apache2ctl configtest
sudo systemctl reload apache2
```

## Network Diagnostics

```bash
# Check if backend port is listening
ss -tlnp | grep $PORT

# Test from localhost
curl http://127.0.0.1:$PORT/health

# Test via Apache
curl https://staff.kalx.berkeley.edu/pass-giveaway/api/health

# Check Netbird
sudo netbird status

# Test DNS
nslookup staff.kalx.berkeley.edu
dig staff.kalx.berkeley.edu

# Check SSL certificate
openssl s_client -connect staff.kalx.berkeley.edu:443 -servername staff.kalx.berkeley.edu
```

## Performance Checks

```bash
# Check resource usage
top
htop

# Check disk space
df -h

# Check memory
free -h

# Check service resource usage
systemctl --user status $SERVICE
```

## Emergency Procedures

### Complete Service Restart

```bash
# Restart backend
systemctl --user restart $SERVICE

# Verify
systemctl --user status $SERVICE

# Restart Apache (if auth issues)
sudo systemctl reload apache2
```

### Rollback Deployment

```bash
# On local machine
git revert HEAD
git push origin main

# This triggers automatic deployment of previous version to staging.
# For production, publish a new release from the reverted commit.
# Monitor in GitHub Actions
```

### Reset Service

```bash
# Stop service
systemctl --user stop $SERVICE

# Clear any locks
rm -f $DEPLOY_PATH/backend/data/*.lock

# Restart service
systemctl --user start $SERVICE
```

## Getting Help

1. **Check logs first**: `journalctl --user -u $SERVICE -n 100`
2. **Review Apache logs**: `sudo tail -50 /var/log/apache2/kalx-staff-error.log` (auth issues: `kalx-auth-error.log`; staging equivalents are prefixed `kalx-stage-`)
3. **Check GitHub Actions**: For deployment issues
4. **Create issue**: In GitHub repository with logs and error messages

## Useful Aliases

Add to `~/.bashrc` for convenience:

```bash
# Production
alias rtp-status='systemctl --user status promotions-app-backend-production'
alias rtp-restart='systemctl --user restart promotions-app-backend-production'
alias rtp-logs='journalctl --user -u promotions-app-backend-production -f'
alias rtp-health='curl http://127.0.0.1:8420/health'
alias rtp-backup='cp ~/promotions-app-production/backend/data/promotions.db ~/promotions-app-production/backend/data/backup_$(date +%Y%m%d_%H%M%S).db'

# Staging
alias rts-status='systemctl --user status promotions-app-backend-staging'
alias rts-restart='systemctl --user restart promotions-app-backend-staging'
alias rts-logs='journalctl --user -u promotions-app-backend-staging -f'
alias rts-health='curl http://127.0.0.1:8421/health'
alias rts-backup='cp ~/promotions-app-staging/backend/data/promotions.db ~/promotions-app-staging/backend/data/backup_$(date +%Y%m%d_%H%M%S).db'
```

Then reload: `source ~/.bashrc`
