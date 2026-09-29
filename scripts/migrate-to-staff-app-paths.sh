#!/usr/bin/env bash
#
# One-time server migration from the old "promotions-app" names to the
# "staff-app" names. Runs on the server as the staff-app user.
#
#   ~/promotions-app-<env>                    -> ~/staff-app-<env>
#   promotions-app-backend-<env>.service      -> staff-app-backend-<env>.service
#   backend/data/promotions.db                -> backend/data/staff-app.db
#
# Idempotent: does nothing once ~/staff-app-<env> exists. The deploy workflow
# runs it before every deploy, so merging/releasing the rename performs the
# migration automatically. It can also be run by hand:
#
#   ssh staff-app@<server> bash -s -- staging < scripts/migrate-to-staff-app-paths.sh
#
# It leaves a symlink at the old deploy path so the Apache Alias/Directory
# blocks (which are root-owned and not deployed by CI) keep serving the
# frontend until they are updated. See docs/staff-app-rename-runbook.md.
#
# Remove this script, and the workflow step that calls it, once both
# environments have been migrated and the symlinks removed.

set -euo pipefail

ENV_NAME="${1:?Usage: $0 production|staging}"
case "$ENV_NAME" in
  production|staging) ;;
  *) echo "ERROR: environment must be 'production' or 'staging'" >&2; exit 1 ;;
esac

OLD_PATH="$HOME/promotions-app-$ENV_NAME"
NEW_PATH="$HOME/staff-app-$ENV_NAME"
OLD_SERVICE="promotions-app-backend-$ENV_NAME"
SYSTEMD_USER_PATH="$HOME/.config/systemd/user"

if [ -e "$NEW_PATH" ]; then
  echo "$NEW_PATH already exists; nothing to migrate"
  exit 0
fi
if [ ! -d "$OLD_PATH" ] || [ -L "$OLD_PATH" ]; then
  echo "No $OLD_PATH directory; nothing to migrate (fresh install)"
  exit 0
fi

set -x

# Stop and remove the old unit. The new unit is installed and started by the
# deploy that follows.
systemctl --user disable --now "$OLD_SERVICE" || true
rm -f "$SYSTEMD_USER_PATH/$OLD_SERVICE.service"
systemctl --user daemon-reload

mv "$OLD_PATH" "$NEW_PATH"
ln -s "$NEW_PATH" "$OLD_PATH"

if [ -f "$NEW_PATH/backend/data/promotions.db" ]; then
  mv "$NEW_PATH/backend/data/promotions.db" "$NEW_PATH/backend/data/staff-app.db"
fi

# The venv's console scripts (uvicorn, alembic) have the old path baked into
# their shebangs. The deploy that follows recreates it.
rm -rf "$NEW_PATH/backend/venv"

echo "Migrated $OLD_PATH -> $NEW_PATH"
