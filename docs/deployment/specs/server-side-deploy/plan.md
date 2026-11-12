# Implementation Plan: Server-Side Deploys

## Overview

Staging and production deploy the same way. A systemd user service on the
server, `staff-app-deploy@<environment>.service`, does all of it:

- fetches the code from GitHub;
- builds the frontend;
- installs everything and restarts the backend.

The only difference is the timer that starts the service:

- **Production**: a systemd timer at 3:51am Pacific. It's set a few minutes
  before the hour, when GitHub's API is less busy.
- **Staging**: a systemd timer every 2 minutes.

GitHub has no access to the server. The server reads the public repo, using a
read-only GitHub token so it isn't throttled (see "GitHub token"). GitHub
Actions only runs the tests, and the workflow is renamed from "Deploy" to
"Tests".

This replaces the scheduled GitHub Actions deploy, which GitHub started 5 to 10
hours late on each of its first three nights (Nov 7–9, 2026).

## Terms

- **Environment**: `staging` or `production`. It's the systemd instance name,
  and it picks the directory (`~/staff-app-<environment>`), backend service and
  port, as the workflow does today.
- **Target**: the commit a deploy installs.
  - Production: the newest release, the one GitHub marks "Latest".
  - Staging: the newest commit on `main`.
- **Deployed version**: what's live: a release tag for production, a commit SHA
  for staging. It's stored in `~/staff-app-<environment>/DEPLOYED_VERSION`, and
  it's the value the app reports as `APP_VERSION`.
- **CI passed**: the commit's "Run Backend Tests" and "Run Frontend Tests"
  check runs both succeeded.

## What a deploy does

The deploy scripts are standard-library Python, run with the server's system
`python3` (Ubuntu 24.04's 3.12): they build the backend's virtualenv, so they
can't run inside it. Steps 1–4 are in `deploy/fetch.py`, which runs from a
stable copy on the server. Steps 5–10 are in `deploy/install.py`, from the code
being deployed (see "Where the scripts run from"). `deploy/deploy_common.py`
holds what both share, and `deploy/notify.py` sends the failure email.

1. **Choose the target.**
   - Production asks GitHub's API for the newest release.
   - Staging runs `git ls-remote` for `main`. That's a git request rather than
     an API call, so it doesn't count against GitHub's API limit.
2. **Stop if it's already deployed.** If the target matches
   `DEPLOYED_VERSION`, exit successfully without logging anything. Staging does
   this on almost every run, every 2 minutes, so these runs must stay silent.
3. **Check the target.**
   - **Production**:
     - If the target is an older release than `DEPLOYED_VERSION`, refuse and
       send a failure email (see "Older Latest release" below).
     - If CI is still running, exit quietly and try again the next night,
       when it will have passed.
     - If CI failed, send a failure email naming the release, and don't deploy
       it. Otherwise a release that can never deploy would go unnoticed.
     - If CI never ran for the release's commit (GitHub has no check runs for
       it at all), treat it like a failure. Releases made before every push
       ran CI can have this, such as v1.13.1, whose commit only changed
       `CHANGELOG.md`.
   - **Staging**:
     - If CI is still running, exit quietly and try again on the next run.
     - If CI failed, exit quietly and stay on the current version. GitHub has
       already emailed about the failed run.
     - Staging only ever deploys the newest commit on `main`. When quick pushes
       leave an earlier commit passing but the newest one failing, it waits for
       a passing `main`.
   - Staging remembers the commit it last checked and the result, so it only
     calls the API for a commit it hasn't settled yet. That's a few calls per
     push.
   - **A target whose deploy already failed:**
     - Staging doesn't retry it until `main` moves on, or you run it with
       `--force`. Without this, a broken commit would send a failure email
       every 2 minutes.
     - Production does retry a release whose deploy failed and was rolled back,
       but only on the next night's run, so a passing problem (such as a
       network error during `npm ci`) sorts itself out. That's at most one email
       a night.
4. **Fetch the code.** Run `git fetch` in a clone at `~/staff-app-src`, then
   `git archive <sha>` into a fresh build directory,
   `~/staff-app-build/<environment>`.
5. **Build the frontend** in that directory with Node from `~/opt`.
   First make sure Node is current (see "Keeping Node up to date"), then run
   `npm ci` and `vite build`. Production sets
   `VITE_RELEASE_VERSION=<tag>`. Staging sets `VITE_COMMIT_SHA=<sha>` and adds
   `--mode staging`. TypeScript checking is skipped because CI already ran it.
6. **Back up the database**, as the workflow does today, and remember the
   backup's name for rollback. Then delete old backups: each environment keeps
   every backup newer than a set number of days, and always its newest few
   however old they are (`BACKUP_RETENTION` in `install.py`: staging 7 days and
   at least 5, production 30 days and at least 10).
7. **Install the new code.**
   - Copy the backend (with today's excludes) and `frontend/dist` into
     `~/staff-app-<environment>` with `rsync --delete`. This keeps the current
     layout, so Apache and the backend units don't change.
   - Run `pip install` into the existing venv, then `alembic upgrade head`.
8. **Set `APP_VERSION`.** Replace only the `APP_VERSION=` line in
   `backend/.env`. Every other setting is left alone (see "Settings").
9. **Update systemd and restart.** Copy `systemd/*.service` and `*.timer` into
   `~/.config/systemd/user/`. Run `daemon-reload`, enable the backend service
   and both deploy timers, then restart the backend.
10. **Verify and finish.**
    - Wait until the backend service is active and `/health` answers, as the
      workflow does today.
    - Write `DEPLOYED_VERSION` and copy the new stable scripts into place.
    - For production, send the "deployed" email.

Any failing step exits with an error. That fails the service, which sends the
failure email. A failure in steps 7–10 on production also triggers a rollback
first.

Two starts of the same instance never run at once. When a deploy is still
running, systemd doesn't start another for that environment, so the staging
timer just waits for it. Staging and production can run at the same time,
which is fine with 2.4 GiB of memory free.

### Rollback (production only)

Before step 7, a production deploy copies what's live (the backend code, the
frontend build and its systemd units) to `~/staff-app-build/production-previous`.
If any of steps 7–10 then fails, `install.py`:

1. stops the backend and puts back the database backup from step 6;
2. copies the saved code and units back, and runs `pip install` for them. No
   migrations are needed, because the restored database already matches them,
   and nothing is downloaded or rebuilt;
3. puts back `APP_VERSION`, restarts the backend and checks `/health`.

The failure email then says whether production was rolled back and is up, or
whether the rollback failed and production may be down. Anything written to
the database between the backup and the rollback is lost; at 3:51am that's
mostly background job records.

Staging doesn't roll back. A broken staging deploy stays as it is for you to
look at, and the failure email tells you.

### Older "Latest" release

If the release marked "Latest" is older than `DEPLOYED_VERSION` (someone
marked an older release as Latest), production refuses to deploy it and sends
a failure email. An older release's code may not work with the newer database
schema. Going back a version is done deliberately, over SSH, with `--ref`.

### When GitHub can't be reached

- **Staging**: no email. It tries again on the next run, and catches up once
  GitHub answers.
- **Production**: the failure email says the 3:51am run couldn't check for a
  new release, so a waiting release doesn't go unnoticed.

## GitHub token

The server sends its GitHub API requests with a token, which raises the limit
from 60 to 5,000 requests an hour. Those requests are the newest release and a
commit's check runs. Without a token, a few quick pushes, or another program on
the server calling GitHub, could use up the 60.

- **Kind of token**: a fine-grained personal access token with **Repository
  access: Public repositories (read-only)** and no permissions added. It can
  read only what anyone can already see, so if it leaked, the only harm would
  be someone else using up its rate limit.
- **Where it's kept**: `~/.config/staff-app-deploy/github-token`, readable only
  by `staff-app` (mode 600). Both environments share it. It isn't in `.env`,
  because the app doesn't use it.
- **Fetching code**: `git ls-remote` and `git fetch` don't use it, because
  reading a public repo over git needs no token.
- **When it expires or is revoked**: fine-grained tokens expire, at most a year
  after they're made unless the organization allows longer. When GitHub
  rejects the token:
  - the scripts carry on without it, so deploys don't stop;
  - they send one email a day saying the token needs replacing. This is the one
    GitHub problem that does email from staging, because it's something you can
    fix.
- **No token file**: the scripts work without a token, at the lower limit.

## Keeping Node up to date

Node runs on the server only while a deploy builds the frontend. It runs no
server and isn't reachable from the network. So it only has to be current when
a build runs, which is exactly when the deploy can update it.

- **Which major version**: a new file, `frontend/.node-version`, holds the
  major version (`26`). CI reads it too (`setup-node`'s `node-version-file`),
  so the server and CI always build with the same major. Moving to Node 28 is
  a one-line change that both pick up.
- **Updating within that major**: before each build, `install.py`:
  1. reads the Node release list from `https://nodejs.org/dist/index.json`, at
     most once a day;
  2. if a newer 26.x exists, downloads its `linux-x64` tarball and
     `SHASUMS256.txt`, and checks the tarball's SHA-256 against it;
  3. unpacks it into `~/opt/node-v26.x.y`;
  4. keeps the previous version, deletes any older ones, and logs the change.

  Each build uses the newest installed version of its major, so staging can
  move to a new major before production does without either disturbing the
  other. Both environments share `~/opt`, under a lock.

  CI's `setup-node` also uses the newest 26.x, so the server builds with the
  same Node as the tests did, including security fixes, usually within a day.
- **If nodejs.org can't be reached**: the build carries on with the Node
  already installed. It only fails if no Node is installed at all.
- **First install**: there's no manual step. The first deploy finds no Node
  and installs it.
- **End of support**: Node 26 is supported until April 2029. Moving to a newer
  major before then is a code change to `frontend/.node-version`, not a server
  task.

## Where the scripts run from

A script deploying the code it was just fetched from has to start from
somewhere stable. The deploy is split in two:

- **`deploy/fetch.py`** (steps 1–4) is installed, with `notify.py` and
  `deploy_common.py`, in `~/staff-app-deploy/<environment>/`, and the unit
  runs it from there. After a successful deploy, `install.py` replaces those
  copies with the new versions.
- **`deploy/install.py`** (steps 5–10, plus rollback) runs from the code just
  fetched, so an install change takes effect on the deploy that ships it.

A change to `fetch.py` takes effect from the deploy after the one that ships
it. Each environment has its own copies, so a push to `main` never changes
what production's nightly run executes; only a production deploy does.

## systemd units (`systemd/`)

- **`staff-app-deploy@.service`**:
  - `Type=oneshot` and
    `ExecStart=/usr/bin/python3 %h/staff-app-deploy/%i/fetch.py %i`.
  - `TimeoutStartSec=30min`.
  - `OnFailure=staff-app-deploy-failed@%i.service`.
- **`staff-app-deploy-production.timer`**:
  - `OnCalendar=*-*-* 03:51:00 America/Los_Angeles`, which follows daylight
    saving. 3:51 is never in the hour skipped when the clocks go forward
    (2–3am).
  - `Persistent=false`, so a run missed during a reboot is skipped rather than
    run at midday.
- **`staff-app-deploy-staging.timer`**: `OnCalendar=*:0/2` (every 2 minutes), with
  `Persistent=false`.
- **`staff-app-deploy-failed@.service`**: sends the failure email.

These are user units under `staff-app`, like the backend services, so they
need no root. They rely on lingering being on for `staff-app`, which it already
must be for the backend to run without a login.

## Emails

Sent to `WEBMASTER_EMAIL`, read from that environment's `.env`, through the
server's local SMTP relay (`LOCAL_SMTP_HOST`, default `localhost:25`). The
sender is a short Python script using the standard library's `smtplib`. It
doesn't use the app's own email code, because that code may be what broke.

| Event | Email |
|---|---|
| A deploy fails (either environment) | Yes, with the environment, the target, the outcome (for production, whether it rolled back) and the last 100 log lines |
| Production deploys a new release | Yes, a short note naming the release |
| Production refuses an older Latest release | Yes, as a failure |
| Production's 3:51am run can't reach GitHub | Yes, as a failure |
| GitHub rejects the token (either environment) | Yes, at most once a day |
| The newest release's CI failed | Yes, as a failure, naming the release, each night until a newer release passes |
| CI never ran for the newest release's commit | Yes, as a failure, naming the release and commit, each night until a newer release passes |
| The newest release's CI is still running at 3:51am | No (it deploys the next night) |
| Staging CI failed or is still running | No |
| Staging can't reach GitHub | No |
| Nothing new to deploy | No |

## Settings (`.env`)

Each environment's `backend/.env` stops being generated on every deploy. The
files the workflow last wrote are already on the server, so they become the
source of truth and are edited by hand from then on.

- **Deploys only change `APP_VERSION`.**
- **Turning a sub-site on** (for example `WORKFORMS_ENABLED`) becomes an
  `.env` edit plus a backend restart.
- **Adding a new setting** to a release means editing `.env` on the server
  before or right after that release deploys. The release notes should say so.

## GitHub Actions (`.github/workflows/tests.yml`, formerly `deploy.yml`)

- **Renamed** from "Deploy" to "Tests". The file can be renamed to `tests.yml`
  too.
- **Removed**:
  - the `schedule` trigger and the `check-release` job;
  - `paths-ignore`, so CI runs on every push, which the CI check depends on.
    Docs-only pushes then also restart staging, which is harmless;
  - the frontend build and artifact upload in `test-frontend`;
  - the whole deploy job: Netbird, SSH, `.env`, deployment records and the
    `staging` and `production` environments.
- **Changed**: `setup-node` reads the Node version from
  `frontend/.node-version` instead of `node-version: '26'`.
- **Kept**:
  - the test jobs on every push to `main`;
  - `workflow_dispatch` as a button that only runs the tests, without the
    `deploy_production` input.

You'll clean up the GitHub secrets, variables, environments and the server's
deploy key yourself afterwards.

## Manual deploys

These steps also go in `README.md` (see "Docs to update"). SSH in as
`staff-app`:

- `systemctl --user start staff-app-deploy@production` deploys the newest
  release now, if it isn't already live.
- `~/staff-app-deploy/production/fetch.py production --force` redeploys it.
- `~/staff-app-deploy/production/fetch.py production --ref v1.12.2 --force` deploys a
  specific release, which is how to go back a version.

- `~/staff-app-deploy/staging/fetch.py staging --force` redeploys staging's newest
  commit, for example after a failed deploy you've fixed on the server.
- `systemctl --user list-timers 'staff-app-deploy-*'` shows when each deploy
  runs next and last ran.
- `journalctl --user -u staff-app-deploy@production` shows the deploy logs.
- `cat ~/staff-app-production/DEPLOYED_VERSION` shows what's live.

Running `fetch.py` directly bypasses systemd, so no failure email is sent; the
output is on screen instead.

## Removed

- **`scripts/deploy-staging.sh`**: retired. Staging only ever runs committed
  code from `main`, and you test locally with the `run-staff-app` skill.

## One-time server setup

All as the `staff-app` user. Node needs no setup step, because the first
deploy installs it.

1. Make sure `git` and `rsync` are installed, then run
   `git clone https://github.com/kalx-berkeley/staff-app.git ~/staff-app-src`.
2. Create the GitHub token (see "GitHub token") and save it:
   `install -D -m 600 /dev/stdin ~/.config/staff-app-deploy/github-token`,
   then paste the token, press Enter and press Ctrl-D.
3. Check what each environment has live (see "Starting `DEPLOYED_VERSION`"
   below).
4. Copy `deploy/fetch.py`, `notify.py` and `deploy_common.py` into
   `~/staff-app-deploy/staging/` and `~/staff-app-deploy/production/`, and the
   new units into `~/.config/systemd/user/`. Check them with
   `systemd-analyze --user verify`. `SETUP_GUIDE.md` ("Deploy Setup") has the
   exact commands.
5. Run `daemon-reload` and enable both deploy timers with
   `systemctl --user enable --now`.
6. Check `loginctl show-user staff-app -p Linger` says `yes`, and send a test
   message through the local SMTP relay to `WEBMASTER_EMAIL`.

### Starting `DEPLOYED_VERSION`

The old workflow already records what it deployed: each deploy writes
`APP_VERSION` into `backend/.env` (it has since v1.12.0). Production's is the
release tag, and staging's is the commit SHA. So when `DEPLOYED_VERSION` is
missing, `fetch.py` starts it from `APP_VERSION`, and there's nothing to write
by hand. Step 3 is just a check that the starting values are right:

```bash
grep '^APP_VERSION=' ~/staff-app-production/backend/.env   # e.g. APP_VERSION=v1.13.1
grep '^APP_VERSION=' ~/staff-app-staging/backend/.env      # e.g. APP_VERSION=<40-character SHA>
```

- **Production**: should show the release you last deployed. GitHub's
  deployment history (the repo's **Deployments** page, `production`) shows the
  same.
- **Staging**: should show a full commit SHA from `main`.
- **If a line is missing or empty**: that environment hasn't been deployed
  since v1.12.0. Write the value yourself, for example
  `echo v1.13.1 > ~/staff-app-production/DEPLOYED_VERSION`.
- **If both `DEPLOYED_VERSION` and `APP_VERSION` are missing**: `fetch.py`
  refuses to deploy and says so. It never treats "unknown" as "deploy now".

## Cutover

One change switches everything over. The new workflow no longer deploys, so
nothing else deploys alongside the timers.

1. Push the change. From then on GitHub deploys nothing, so staging and
   production stay as they are until the timers are on. Production keeps the
   release it has.
2. Do the one-time server setup above. It clones from GitHub, so it needs the
   change pushed first.
3. Staging's `DEPLOYED_VERSION` starts from the commit the old workflow
   deployed, so within 2 minutes of turning the timers on, staging deploys the
   pushed change. That's the first deploy through the new path.
4. Check staging, including `/api/version` and the open-tab reload.
5. Leave production to the next 3:51am run, or start it by hand at a quiet
   time. There's only something to deploy once a new release is published.
   The next morning, check the "deployed" email arrived and that the timer
   fired on time (`systemctl --user list-timers`).

## Docs to update

- `README.md`:
  - Rewrite the Deployment section as "how to deploy":
    - when each environment deploys and how to tell what's live;
    - the manual deploy, redeploy and go-back-a-version commands from "Manual
      deploys";
    - where the logs are, and what the emails mean;
    - how to replace the GitHub token.
  - Remove the GitHub secrets and variables list, which only the old deploy
    used.
- `SETUP_GUIDE.md`: GitHub Actions deployment setup, "`.env` is generated
  automatically", and deployment operations.
- `systemd/README.md`.
- This repo's `CLAUDE.md`: it lists `scripts/deploy-staging.sh` and
  `.github/workflows/deploy.yml` under deployment.
- `docs/pass-giveaway/How-to-remove-the-legacy-import-code.md`: it points at
  the old workflow's `LEGACY_IMPORT_ENABLED` line.

## Testing

- **Scripts**: pytest tests in `deploy/tests/`, which CI runs with the backend
  tests. They cover the target, CI, already-deployed and retry decisions, Node
  updates, rollback, and the emails. `fetch.py --dry-run` prints what it would
  deploy without changing anything.
- **Units**: `systemd-analyze verify` on the units, and `systemd-analyze calendar`
  to confirm the next run times.
- **End to end**: before shipping, the whole deploy was rehearsed in a
  scratch home directory. It used a real git origin, a real Node download,
  `npm ci`, the Vite build, `pip install` and every migration; only `systemctl`
  and GitHub's CI answers were faked. That covered a staging deploy, a quiet
  run with nothing new, a production deploy, and a production release with a
  failing migration, which rolled back. On the server, staging is the real test
  (cutover step 2).
