# Systemd Service Files

This directory contains user systemd service files for the Promotions Pass Giveaway System.
Production and staging run as two independent services on the same server, under separate
deploy directories and separate ports, so a staging deploy can never affect production.

## Services

- `promotions-app-backend-production.service`: Backend API service (uvicorn), port 8420,
  working directory `~/promotions-app-production/backend`
- `promotions-app-backend-staging.service`: Backend API service (uvicorn), port 8421,
  working directory `~/promotions-app-staging/backend`

Both run as the `staff-app` user. The GitHub Actions deploy workflow installs/updates and
restarts the appropriate one automatically (production on a published release, staging on a
push to `main`) — the manual steps below are only needed for first-time server setup.

## Installation

These services are installed as **user services** (not system services).

### Backend Service Installation

```bash
# As staff-app user
mkdir -p ~/.config/systemd/user

# Copy service file(s)
cp promotions-app-backend-production.service ~/.config/systemd/user/
cp promotions-app-backend-staging.service ~/.config/systemd/user/

# Reload systemd
systemctl --user daemon-reload

# Enable services to start at boot
systemctl --user enable promotions-app-backend-production
systemctl --user enable promotions-app-backend-staging

# Start services
systemctl --user start promotions-app-backend-production
systemctl --user start promotions-app-backend-staging
```

### Automatic Installation

These services are automatically installed during deployment by the GitHub Actions workflow.
See [SETUP_GUIDE.md](../SETUP_GUIDE.md) for first-time server setup.

## Managing Services

Substitute `promotions-app-backend-production` or `promotions-app-backend-staging` for
`<service>` below.

### Check Status

```bash
systemctl --user status <service>
```

### Start/Stop/Restart

```bash
systemctl --user start <service>
systemctl --user stop <service>
systemctl --user restart <service>
```

### View Logs

```bash
journalctl --user -u <service> -f
journalctl --user -u <service> -n 50
journalctl --user -u <service> --since "2024-01-15 10:00:00"
```

### Enable/Disable Auto-start

```bash
systemctl --user enable <service>
systemctl --user disable <service>
```

## Service Details

### Backend Services (staff-app user)

| | Production | Staging |
|---|---|---|
| Unit | `promotions-app-backend-production.service` | `promotions-app-backend-staging.service` |
| Port | 8420 (localhost only) | 8421 (localhost only) |
| Working Directory | `~/promotions-app-production/backend` | `~/promotions-app-staging/backend` |
| Command | `uvicorn app.main:app --host 127.0.0.1 --port 8420` | `uvicorn app.main:app --host 127.0.0.1 --port 8421` |

Both: **Type**: Simple, **Restart**: Always (with 10s delay), **Security**: NoNewPrivileges,
PrivateTmp, ProtectSystem=strict

## User Lingering

For the user service to start at boot (before the user logs in), lingering must be enabled:

```bash
# As root
sudo loginctl enable-linger staff-app

# Verify
loginctl show-user staff-app | grep Linger
```

This is done automatically during initial server setup.

## Troubleshooting

Substitute the production or staging service name/path/port as appropriate.

### Service Won't Start

```bash
# Check service status
systemctl --user status <service>

# View detailed logs
journalctl --user -u <service> --no-pager -n 50

# Check if port is already in use (8420 production, 8421 staging)
ss -tlnp | grep 8420
```

### Service Crashes Immediately

```bash
# Check for syntax errors in service file
systemctl --user cat <service>

# Reload systemd after changes
systemctl --user daemon-reload

# Try starting manually to see errors
cd ~/promotions-app-production/backend   # or ~/promotions-app-staging/backend
source venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8420   # or 8421 for staging
```

## Security Features

The backend service includes security hardening:

- **NoNewPrivileges**: Prevents privilege escalation
- **PrivateTmp**: Isolated /tmp directory
- **ProtectSystem**: Read-only system directories
- **ProtectHome**: Read-only home directory (except data dir)
- **ReadWritePaths**: Only backend/data is writable

## Notes

- Both backend services run as the `staff-app` user (non-root)
- Each service binds to localhost only (127.0.0.1), on its own port
- Apache reverse proxies each site to its corresponding service/port
- Services automatically restart on failure
- Logs are managed by systemd journal
- Authentication is handled by Apache `mod_auth_openidc` (Google OAuth2)
