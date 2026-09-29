# Runbook: renaming promotions-app to staff-app on the server

The app started out as the promotions pass-giveaway site and is now the KALX
Staff App, which hosts more than one sub-site. This one-time change renames
its infrastructure on the server:

| Before | After |
|---|---|
| `~/promotions-app-production`, `~/promotions-app-staging` | `~/staff-app-production`, `~/staff-app-staging` |
| `promotions-app-backend-{production,staging}.service` | `staff-app-backend-{production,staging}.service` |
| `backend/data/promotions.db` | `backend/data/staff-app.db` |

"Promotions" is unchanged wherever it names the Promotions department or role
(for example `/pass-giveaway/promotions`).

## What happens automatically

The deploy workflow runs `scripts/migrate-to-staff-app-paths.sh` before each
deploy. The first time it runs in an environment, it:

1. Stops and disables `promotions-app-backend-<env>` and removes its unit file
2. Moves `~/promotions-app-<env>` to `~/staff-app-<env>` and leaves a symlink
   at the old path, so the current Apache config keeps serving the frontend
3. Renames `promotions.db` to `staff-app.db`
4. Deletes the backend venv, whose scripts have the old path baked in

The deploy then continues as usual: it rewrites `.env` with the new
`DATABASE_URL`, rebuilds the venv, and installs and starts
`staff-app-backend-<env>`. The backend is down from step 1 until the new
service starts, which takes about as long as the venv rebuild.

On later deploys the script sees `~/staff-app-<env>` and does nothing.

`scripts/deploy-staging.sh` doesn't install systemd units, so it refuses to
run until the GitHub Actions deploy has migrated staging.

## Steps

### Staging

1. Merge the rename PR to `main`. The staging deploy migrates staging.
2. Check the deploy log's "Migrate promotions-app paths to staff-app" step
   printed `Migrated ...`, and that the deploy passed its health check.
3. On the server, as the `staff-app` user:
   ```bash
   systemctl --user status staff-app-backend-staging
   ls -l ~/promotions-app-staging        # symlink -> ~/staff-app-staging
   ls ~/staff-app-staging/backend/data   # staff-app.db and backups
   ```
4. Update Apache (as root). Copy the updated `apache/sites/staff.stage.conf`
   from this repo into `/etc/apache2/sites-available/`, filling in the same
   placeholders as before, or change `promotions-app-staging` to
   `staff-app-staging` in the `Alias` and `<Directory>` lines of the
   installed file. Then:
   ```bash
   sudo apache2ctl configtest && sudo systemctl reload apache2
   ```
5. Load `https://staff.stage.<domain>/pass-giveaway/` and check it works.
6. Remove the symlink: `rm ~/promotions-app-staging`, then reload the page
   again to confirm Apache no longer needs it.

### Production

Publish a release. Then do steps 2–6 above with `production`,
`staff.conf` and `https://staff.<domain>/`.

### Cleanup

Once both environments are migrated and both symlinks are gone, open a PR
that removes `scripts/migrate-to-staff-app-paths.sh`, the workflow step that
calls it, the migration check in `scripts/deploy-staging.sh`, and this
runbook.

## Rolling back

Before Apache is updated (step 4), the old paths still work through the
symlink. To go back to a pre-rename release in an environment:

```bash
systemctl --user disable --now staff-app-backend-<env>
rm ~/.config/systemd/user/staff-app-backend-<env>.service
rm ~/promotions-app-<env>                            # the symlink
mv ~/staff-app-<env> ~/promotions-app-<env>
mv ~/promotions-app-<env>/backend/data/staff-app.db ~/promotions-app-<env>/backend/data/promotions.db
rm -rf ~/promotions-app-<env>/backend/venv
```

Then redeploy the older release, which reinstalls
`promotions-app-backend-<env>`. If Apache was already updated, revert its
`Alias` and `<Directory>` paths too.
