# Troubleshooting Quick Reference

Quick commands for common issues. For detailed troubleshooting, see [SETUP_GUIDE.md](SETUP_GUIDE.md).

## Quick Diagnostics

```bash
# Check all services
systemctl --user status promotions-app-backend

# Test backend locally
curl http://127.0.0.1:8000/health

# Test via Apache
curl https://staff.kalx.berkeley.edu/pass-giveaway/api/health

# View recent logs
journalctl --user -u promotions-app-backend -n 50
```

## Common Issues

### Service Won't Start

```bash
# View detailed logs
journalctl --user -u promotions-app-backend --no-pager -n 100

# Check for port conflicts
ss -tlnp | grep 8000

# Restart service
systemctl --user restart promotions-app-backend
```

### 502 Bad Gateway

```bash
# Check if backend is running
systemctl --user is-active promotions-app-backend
curl http://127.0.0.1:8000/health

# Check Apache config
sudo apache2ctl configtest

# View Apache errors (staff site handles /api/ proxying)
sudo tail -50 /var/log/apache2/kalx-staff-error.log
```

### Frontend Not Loading

```bash
# Check if files exist
ls -la ~/promotions-app/frontend/dist/

# Fix permissions
chmod 755 ~
chmod 755 ~/promotions-app
chmod 755 ~/promotions-app/frontend
chmod -R 755 ~/promotions-app/frontend/dist

# Check Apache logs
sudo tail -50 /var/log/apache2/kalx-staff-error.log
```

### Authentication Not Working

Google OAuth is handled by two Apache VirtualHosts using `mod_auth_openidc`:
- `auth.kalx.berkeley.edu` — handles the OAuth2 callback from Google
- `staff.kalx.berkeley.edu` — enforces authentication for the app

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
- `OIDCClientID` or `OIDCClientSecret` incorrect — must be identical in **both** VirtualHost blocks
- `OIDCCryptoPassphrase` differs between the two VirtualHost blocks — must be identical for session sharing to work
- Redirect URI `https://auth.kalx.berkeley.edu/redirect_uri` not registered in Google Cloud Console
- `OIDCCookieDomain` not set to `.kalx.berkeley.edu` in both VirtualHost blocks

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
ls -la ~/promotions-app/backend/data/promotions.db

# Backup database
cp ~/promotions-app/backend/data/promotions.db \
   ~/promotions-app/backend/data/backup_$(date +%Y%m%d_%H%M%S).db

# Restart backend
systemctl --user restart promotions-app-backend
```

## Service Management

```bash
# Start service
systemctl --user start promotions-app-backend

# Stop service
systemctl --user stop promotions-app-backend

# Restart service
systemctl --user restart promotions-app-backend

# View status
systemctl --user status promotions-app-backend

# Enable/disable auto-start
systemctl --user enable promotions-app-backend
systemctl --user disable promotions-app-backend
```

## Log Management

```bash
# Follow logs in real-time
journalctl --user -u promotions-app-backend -f

# Last N lines
journalctl --user -u promotions-app-backend -n 100

# Since specific time
journalctl --user -u promotions-app-backend --since "2024-01-15 10:00:00"

# Between times
journalctl --user -u promotions-app-backend --since "10:00" --until "11:00"

# Search logs
journalctl --user -u promotions-app-backend | grep -i error

# Apache logs — auth site (OAuth2 callback)
sudo tail -f /var/log/apache2/kalx-auth-access.log
sudo tail -f /var/log/apache2/kalx-auth-error.log

# Apache logs — staff site (app, API proxy)
sudo tail -f /var/log/apache2/kalx-staff-access.log
sudo tail -f /var/log/apache2/kalx-staff-error.log
```

## Database Operations

```bash
# Backup database
cp ~/promotions-app/backend/data/promotions.db \
   ~/promotions-app/backend/data/backup_$(date +%Y%m%d).db

# Restore database
systemctl --user stop promotions-app-backend
cp ~/promotions-app/backend/data/backup_YYYYMMDD.db \
   ~/promotions-app/backend/data/promotions.db
systemctl --user start promotions-app-backend

# Check database integrity
cd ~/promotions-app/backend
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
nano ~/promotions-app/backend/.env
systemctl --user restart promotions-app-backend

# Edit Apache config (requires root/sudo)
# Both auth and staff VirtualHosts are in the same file.
# Remember: OIDCClientID, OIDCClientSecret, and OIDCCryptoPassphrase
# must be identical in both VirtualHost blocks.
sudo nano /etc/apache2/sites-available/auth.kalx.conf
sudo nano /etc/apache2/sites-available/staff.kalx.conf
sudo apache2ctl configtest
sudo systemctl reload apache2
```

## Network Diagnostics

```bash
# Check if backend port is listening
ss -tlnp | grep 8000

# Test from localhost
curl http://127.0.0.1:8000/health

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
systemctl --user status promotions-app-backend
```

## Emergency Procedures

### Complete Service Restart

```bash
# Restart backend
systemctl --user restart promotions-app-backend

# Verify
systemctl --user status promotions-app-backend

# Restart Apache (if auth issues)
sudo systemctl reload apache2
```

### Rollback Deployment

```bash
# On local machine
git revert HEAD
git push origin main

# This triggers automatic deployment of previous version
# Monitor in GitHub Actions
```

### Reset Service

```bash
# Stop service
systemctl --user stop promotions-app-backend

# Clear any locks
rm -f ~/promotions-app/backend/data/*.lock

# Restart service
systemctl --user start promotions-app-backend
```

## Getting Help

1. **Check logs first**: `journalctl --user -u promotions-app-backend -n 100`
2. **Review Apache logs**: `sudo tail -50 /var/log/apache2/kalx-staff-error.log` (auth issues: `kalx-auth-error.log`)
3. **Check GitHub Actions**: For deployment issues
4. **Create issue**: In GitHub repository with logs and error messages

## Useful Aliases

Add to `~/.bashrc` for convenience:

```bash
# Service management
alias rt-status='systemctl --user status promotions-app-backend'
alias rt-restart='systemctl --user restart promotions-app-backend'
alias rt-logs='journalctl --user -u promotions-app-backend -f'

# Health checks
alias rt-health='curl http://127.0.0.1:8000/health'

# Database backup
alias rt-backup='cp ~/promotions-app/backend/data/promotions.db ~/promotions-app/backend/data/backup_$(date +%Y%m%d_%H%M%S).db'
```

Then reload: `source ~/.bashrc`
