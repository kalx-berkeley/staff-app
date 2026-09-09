# Systemd Service Files

This directory contains user systemd service files for the Promotions Pass Giveaway System.

## Services

- `promotions-app-backend.service`: Backend API service (uvicorn) - runs as `staff-app` user

## Installation

These services are installed as **user services** (not system services).

### Backend Service Installation

```bash
# As staff-app user
mkdir -p ~/.config/systemd/user

# Copy service file
cp promotions-app-backend.service ~/.config/systemd/user/

# Reload systemd
systemctl --user daemon-reload

# Enable service to start at boot
systemctl --user enable promotions-app-backend

# Start service
systemctl --user start promotions-app-backend
```

### Automatic Installation

This service is automatically installed during the initial server setup. See [SETUP_GUIDE.md](../SETUP_GUIDE.md) for details.

## Managing Services

### Check Status

```bash
systemctl --user status promotions-app-backend
```

### Start/Stop/Restart

```bash
systemctl --user start promotions-app-backend
systemctl --user stop promotions-app-backend
systemctl --user restart promotions-app-backend
```

### View Logs

```bash
journalctl --user -u promotions-app-backend -f
journalctl --user -u promotions-app-backend -n 50
journalctl --user -u promotions-app-backend --since "2024-01-15 10:00:00"
```

### Enable/Disable Auto-start

```bash
systemctl --user enable promotions-app-backend
systemctl --user disable promotions-app-backend
```

## Service Details

### Backend Service (staff-app user)

- **Type**: Simple
- **Port**: 8420 (localhost only)
- **Working Directory**: `~/promotions-app/backend`
- **Command**: `uvicorn app.main:app --host 127.0.0.1 --port 8420`
- **Restart**: Always (with 10s delay)
- **Security**: NoNewPrivileges, PrivateTmp, ProtectSystem=strict

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

### Service Won't Start

```bash
# Check service status
systemctl --user status promotions-app-backend

# View detailed logs
journalctl --user -u promotions-app-backend --no-pager -n 50

# Check if port is already in use
ss -tlnp | grep 8420
```

### Service Crashes Immediately

```bash
# Check for syntax errors in service file
systemctl --user cat promotions-app-backend

# Reload systemd after changes
systemctl --user daemon-reload

# Try starting manually to see errors
cd ~/promotions-app/backend
source venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8420
```

## Security Features

The backend service includes security hardening:

- **NoNewPrivileges**: Prevents privilege escalation
- **PrivateTmp**: Isolated /tmp directory
- **ProtectSystem**: Read-only system directories
- **ProtectHome**: Read-only home directory (except data dir)
- **ReadWritePaths**: Only backend/data is writable

## Notes

- Backend service runs as the `staff-app` user (non-root)
- Service binds to localhost only (127.0.0.1)
- Apache reverse proxies to this service
- Service automatically restarts on failure
- Logs are managed by systemd journal
- Authentication is handled by Apache `mod_auth_openidc` (Google OAuth2)
