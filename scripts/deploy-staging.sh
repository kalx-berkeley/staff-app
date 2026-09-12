#!/usr/bin/env bash
#
# Deploy the current working tree to staging without committing/pushing.
# Mirrors the "test" + "deploy" jobs in .github/workflows/deploy.yml, but:
#   - runs against your local venv/node_modules instead of a fresh install
#   - assumes Netbird is already connected and your SSH key is already in
#     the staff-app user's authorized_keys
#   - leaves the server's existing backend/.env alone (it holds secrets that
#     only GitHub Actions writes)
#
# Usage: NETBIRD_HOSTNAME=<staging-peer-name> ./scripts/deploy-staging.sh

set -euo pipefail

NETBIRD_HOSTNAME="${NETBIRD_HOSTNAME:?Set NETBIRD_HOSTNAME to the Netbird peer name of the staging server}"
DEPLOY_USER=staff-app
DEPLOY_PATH=/home/staff-app/promotions-app-staging
SERVICE_NAME=promotions-app-backend-staging
BACKEND_PORT=8421

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
FRONTEND_DIR="$REPO_ROOT/frontend"
SSH_OPTS=(-o BatchMode=yes)

log() { echo -e "\n==> $*"; }
connecting() { echo "    (connecting via SSH...)"; }

log "Checking backend/venv Python version"
if [ ! -x "$BACKEND_DIR/venv/bin/python3" ]; then
  echo "ERROR: $BACKEND_DIR/venv has no python3 — create it first:" >&2
  echo "  cd backend && python3.14 -m venv venv && venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi
# Read the version CI tests against from deploy.yml so this check can't drift
# out of sync with it.
REQUIRED_PY_VERSION="$(grep -A3 'Set up Python$' "$REPO_ROOT/.github/workflows/deploy.yml" \
  | grep 'python-version:' | head -1 | sed -E "s/.*python-version:\s*'?([0-9]+\.[0-9]+)'?.*/\1/")"
if [ -z "$REQUIRED_PY_VERSION" ]; then
  echo "ERROR: couldn't find python-version in the 'Set up Python' step of .github/workflows/deploy.yml" >&2
  echo "(the step may have been renamed/reformatted — update the grep in this script to match)" >&2
  exit 1
fi
VENV_PY_VERSION="$("$BACKEND_DIR/venv/bin/python3" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
if [ "$VENV_PY_VERSION" != "$REQUIRED_PY_VERSION" ]; then
  echo "ERROR: backend/venv is Python $VENV_PY_VERSION but CI tests against Python $REQUIRED_PY_VERSION." >&2
  echo "This is also a symptom of a venv built inside a different environment than the one running this" >&2
  echo "script (e.g. built inside a Claude Code sandbox, now running on your host, or vice versa)." >&2
  echo "Rebuild it: cd backend && rm -rf venv && python$REQUIRED_PY_VERSION -m venv venv && venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

log "Running backend tests"
(
  cd "$BACKEND_DIR"
  source venv/bin/activate
  pip install -q -r requirements.txt
  black --check .
  pytest --cov=app --cov-report=xml
)

log "Running frontend tests"
(
  cd "$FRONTEND_DIR"
  npm install --no-audit --no-fund
  npm run lint
  npx tsc --noEmit
  npm test
)

log "Resolving Netbird IP of staging server ($NETBIRD_HOSTNAME)"
STATUS="$(sudo netbird status --filter-by-names "$NETBIRD_HOSTNAME" --filter-by-status connected --json)"
SSH_HOST="$(echo "$STATUS" | jq --raw-output '.peers.details[0].netbirdIp')"
if [ -z "$SSH_HOST" ] || [ "$SSH_HOST" == "null" ]; then
  echo "Could not resolve a connected Netbird peer named '$NETBIRD_HOSTNAME'. Is Netbird connected?" >&2
  exit 1
fi
echo "staging host: $SSH_HOST"

log "Building frontend (staging mode)"
(
  cd "$FRONTEND_DIR"
  VITE_COMMIT_SHA="local-$(git -C "$REPO_ROOT" rev-parse --short HEAD)-$(date +%s)" npm run build:staging
)

log "Backing up remote database"
connecting
ssh "${SSH_OPTS[@]}" "$DEPLOY_USER@$SSH_HOST" bash <<ENDSSH
set -e
mkdir -p "$DEPLOY_PATH/backend/data"
mkdir -p "$DEPLOY_PATH/frontend/dist"
if [ -f "$DEPLOY_PATH/backend/data/promotions.db" ]; then
  cp "$DEPLOY_PATH/backend/data/promotions.db" \
     "$DEPLOY_PATH/backend/data/backup_\$(date +%Y%m%d_%H%M%S).db"
fi
ENDSSH

log "Syncing backend code"
connecting
rsync --recursive --links --perms --times --itemize-changes --compress --delete \
  --exclude='venv' \
  --exclude='__pycache__' \
  --exclude='.pytest_cache' \
  --exclude='*.pyc' \
  --exclude='.coverage' \
  --exclude='test*.db' \
  --exclude='data' \
  --exclude='.env' \
  "$BACKEND_DIR/" "$DEPLOY_USER@$SSH_HOST:$DEPLOY_PATH/backend/"

log "Syncing frontend build"
connecting
rsync --recursive --links --perms --times --itemize-changes --compress --delete \
  "$FRONTEND_DIR/dist/" "$DEPLOY_USER@$SSH_HOST:$DEPLOY_PATH/frontend/dist/"

log "Installing backend dependencies and running migrations"
connecting
ssh "${SSH_OPTS[@]}" "$DEPLOY_USER@$SSH_HOST" bash <<ENDSSH
set -e
cd "$DEPLOY_PATH/backend"
python3 -m venv venv
venv/bin/pip install --upgrade pip -q
venv/bin/pip install -r requirements.txt -q
venv/bin/alembic upgrade head
ENDSSH

log "Restarting $SERVICE_NAME"
connecting
ssh "${SSH_OPTS[@]}" "$DEPLOY_USER@$SSH_HOST" bash <<ENDSSH
set -e
systemctl --user daemon-reload
systemctl --user restart "$SERVICE_NAME"
ENDSSH

log "Verifying deployment"
connecting
ssh "${SSH_OPTS[@]}" "$DEPLOY_USER@$SSH_HOST" bash <<ENDSSH
set -e
for i in \$(seq 1 15); do
  if curl -sf "http://127.0.0.1:$BACKEND_PORT/health" >/dev/null; then
    echo "Backend healthy"
    exit 0
  fi
  sleep 2
done
echo "ERROR: backend health check failed" >&2
exit 1
ENDSSH

log "Deployed local working tree to staging"
