#!/usr/bin/env python3
"""
Install the code this file came with into an environment.

``fetch.py`` runs this from the build directory it has just filled, so an
install change takes effect on the deploy that ships it. It:

1. makes sure Node is current, and builds the frontend;
2. backs up the database;
3. copies the backend and frontend into place, installs the backend's
   dependencies and runs the migrations;
4. sets ``APP_VERSION``, updates the systemd units and restarts the backend;
5. checks the backend is healthy, then records the new version.

Nothing on the server changes until step 2. If anything from step 3 on fails
in production, it rolls production back to what was live before. Staging is
left as it is for someone to look at.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import logging
import os
import platform
import re
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from deploy_common import (
    BACKEND_RSYNC_FILTERS,
    Environment,
    config_home,
    env_file,
    get_environment,
    locked,
    record_failure,
    run,
    send_email,
    setup_logging,
    write_atomically,
)

logger = logging.getLogger("staff-app-deploy")

NODE_DIST = "https://nodejs.org/dist"
NODE_VERSION = re.compile(r"^node-v(\d+)\.(\d+)\.(\d+)-linux-x64$")
# Installed Node versions kept for each major: the newest and the one before
NODE_VERSIONS_KEPT = 2
# Files copied to ~/staff-app-deploy/<environment>/ for systemd to run
STABLE_FILES = ("fetch.py", "notify.py", "deploy_common.py")
HEALTH_WAIT_SECONDS = 60


@dataclass
class Snapshot:
    """What production had live before this deploy, for rolling back to."""

    directory: Path
    # systemd unit files that existed before, by name
    units: list[str] = field(default_factory=list)


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """
    Read the command line.

    :param argv: The arguments, or None for ``sys.argv``
    :type argv: Sequence[str] | None
    :returns: The parsed arguments
    :rtype: argparse.Namespace
    """
    parser = argparse.ArgumentParser(description="Install this code into an environment.")
    parser.add_argument("environment", choices=["staging", "production"])
    parser.add_argument(
        "--version", required=True, help="the release tag or commit SHA being installed"
    )
    parser.add_argument(
        "--previous", required=True, help="the version live now, for rolling back to"
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args(argv)


def node_versions(major: int) -> list[Path]:
    """
    List the installed Node versions for a major, oldest first.

    :param major: The Node major version, such as 26
    :type major: int
    :returns: Their directories under ``~/opt``
    :rtype: list[Path]
    """
    found = []
    for path in (Path.home() / "opt").glob(f"node-v{major}.*-linux-x64"):
        match = NODE_VERSION.match(path.name)
        if match and (path / "bin" / "node").exists():
            found.append((tuple(map(int, match.groups())), path))
    return [path for _, path in sorted(found)]


def download(url: str, destination: Path) -> None:
    """
    Download a file.

    :param url: Where it is
    :type url: str
    :param destination: Where to save it
    :type destination: Path
    :returns: None
    :rtype: None
    """
    request = urllib.request.Request(url, headers={"User-Agent": "kalx-staff-app-deploy"})
    with (
        urllib.request.urlopen(request, timeout=300) as response,
        destination.open("wb") as out,
    ):
        shutil.copyfileobj(response, out)


def install_node(version: str) -> Path:
    """
    Download, check and unpack one Node release into ``~/opt``.

    :param version: The release, such as ``v26.1.0``
    :type version: str
    :returns: The new version's directory
    :rtype: Path
    :raises ValueError: If the download doesn't match Node's published checksum
    """
    name = f"node-{version}-linux-x64"
    opt = Path.home() / "opt"
    with tempfile.TemporaryDirectory(dir=opt) as temporary:
        work = Path(temporary)
        tarball = work / f"{name}.tar.gz"
        download(f"{NODE_DIST}/{version}/{name}.tar.gz", tarball)
        download(f"{NODE_DIST}/{version}/SHASUMS256.txt", work / "SHASUMS256.txt")
        expected = next(
            (
                line.split()[0]
                for line in (work / "SHASUMS256.txt").read_text().splitlines()
                if line.endswith(f"  {tarball.name}")
            ),
            None,
        )
        actual = hashlib.sha256(tarball.read_bytes()).hexdigest()
        if expected != actual:
            raise ValueError(
                f"{tarball.name}'s SHA-256 is {actual}, but Node publishes {expected}"
            )
        with tarfile.open(tarball) as archive:
            archive.extractall(work / "unpacked", filter="data")
        (work / "unpacked" / name).rename(opt / name)
    logger.info("Installed Node %s in %s", version, opt / name)
    return opt / name


def ensure_node(major: int) -> Path:
    """
    Make sure the newest Node release of a major is installed, at most once a day.

    Node runs only to build the frontend, so keeping it current at build time
    is enough. If nodejs.org can't be reached, the newest installed version is
    used.

    :param major: The Node major version, from ``frontend/.node-version``
    :type major: int
    :returns: The ``bin`` directory to build with
    :rtype: Path
    :raises RuntimeError: If no Node is installed and none can be downloaded
    """
    if platform.machine() != "x86_64":
        raise RuntimeError(f"Node is only installed for x86_64, not {platform.machine()}")
    opt = Path.home() / "opt"
    opt.mkdir(parents=True, exist_ok=True)
    # Both environments may build at once, and share ~/opt
    with locked(opt / ".lock", wait=True):
        checked = opt / f".checked-node-{major}"
        today = datetime.date.today().isoformat()
        installed = node_versions(major)
        if not installed or not checked.exists() or checked.read_text().strip() != today:
            try:
                request = urllib.request.Request(
                    f"{NODE_DIST}/index.json",
                    headers={"User-Agent": "kalx-staff-app-deploy"},
                )
                with urllib.request.urlopen(request, timeout=60) as response:
                    releases = json.load(response)
                newest = next(
                    release["version"]
                    for release in releases
                    if release["version"].startswith(f"v{major}.")
                    and "linux-x64" in release.get("files", [])
                )
                if not (opt / f"node-{newest}-linux-x64" / "bin" / "node").exists():
                    install_node(newest)
                write_atomically(checked, today + "\n")
            except (
                urllib.error.URLError,
                OSError,
                ValueError,
                StopIteration,
                KeyError,
            ) as error:
                if not installed:
                    raise RuntimeError(
                        f"No Node {major} is installed, and installing it failed: {error}"
                    ) from error
                logger.warning(
                    "Couldn't check for a newer Node %s, so %s is used: %s",
                    major,
                    installed[-1].name,
                    error,
                )
            installed = node_versions(major)
            for old in installed[:-NODE_VERSIONS_KEPT]:
                shutil.rmtree(old)
                logger.info("Removed the old %s", old.name)
            installed = installed[-NODE_VERSIONS_KEPT:]
    return installed[-1] / "bin"


def build_frontend(source: Path, environment: Environment, version: str) -> None:
    """
    Build the frontend in the build directory.

    TypeScript isn't checked here, because CI already did before this commit
    could be deployed.

    :param source: The build directory
    :type source: Path
    :param environment: The environment
    :type environment: Environment
    :param version: The release tag or commit SHA, which the build shows
    :type version: str
    :returns: None
    :rtype: None
    """
    frontend = source / "frontend"
    major = int((frontend / ".node-version").read_text().strip().lstrip("v").split(".")[0])
    node_bin = ensure_node(major)
    build_env = dict(
        os.environ, PATH=f"{node_bin}:{os.environ.get('PATH', '/usr/bin:/bin')}"
    )
    vite = [frontend / "node_modules" / ".bin" / "vite", "build"]
    if environment.name == "production":
        build_env["VITE_RELEASE_VERSION"] = version
    else:
        build_env["VITE_COMMIT_SHA"] = version
        vite += ["--mode", "staging"]
    # npm comes with Node, and is updated with it, so its notice to update
    # npm on its own is just noise in the log
    run(
        ["npm", "ci", "--no-audit", "--no-fund", "--no-update-notifier"],
        cwd=frontend,
        env=build_env,
    )
    run(vite, cwd=frontend, env=build_env)


def backup_database(environment: Environment) -> Path | None:
    """
    Copy the database, consistently, before anything changes it.

    :param environment: The environment
    :type environment: Environment
    :returns: The backup, or None when there's no database yet
    :rtype: Path | None
    """
    data = environment.deploy_dir / "backend" / "data"
    database = data / "staff-app.db"
    if not database.exists():
        return None
    backup = data / f"backup_{datetime.datetime.now():%Y%m%d_%H%M%S}.db"
    live = sqlite3.connect(database)
    copy = sqlite3.connect(backup)
    try:
        live.backup(copy)
    finally:
        copy.close()
        live.close()
    logger.info("Backed up the database to %s", backup)
    return backup


def units_for(environment: Environment) -> list[str]:
    """
    The systemd unit files this environment's deploy installs.

    Both environments share the deploy service templates, so only production
    installs them. A change to them reaches the server with a release, not
    with every push to ``main``.

    :param environment: The environment
    :type environment: Environment
    :returns: The unit file names, from the repo's ``systemd/`` folder
    :rtype: list[str]
    """
    units = [
        f"{environment.backend_service}.service",
        f"staff-app-deploy-{environment.name}.timer",
    ]
    if environment.name == "production":
        units += ["staff-app-deploy@.service", "staff-app-deploy-failed@.service"]
    return units


def rsync(source: Path, destination: Path, filters: Sequence[str] = ()) -> None:
    """
    Make a directory match another, deleting what isn't in the source.

    :param source: The directory to copy from
    :type source: Path
    :param destination: The directory to make match it
    :type destination: Path
    :param filters: rsync filter rules, such as ``- venv`` for files to leave
        alone in both
    :type filters: Sequence[str]
    :returns: None
    :rtype: None
    """
    destination.mkdir(parents=True, exist_ok=True)
    run(
        [
            "rsync",
            "--recursive",
            "--links",
            "--perms",
            "--times",
            "--delete",
            *(f"--filter={rule}" for rule in filters),
            f"{source}/",
            f"{destination}/",
        ]
    )


def take_snapshot(environment: Environment) -> Snapshot:
    """
    Copy what production has live, so a failed deploy can put it back.

    :param environment: The environment
    :type environment: Environment
    :returns: Where the copy is, and which unit files it has
    :rtype: Snapshot
    """
    snapshot = Snapshot(environment.snapshot_dir)
    for live, copy, filters in (
        (
            environment.deploy_dir / "backend",
            snapshot.directory / "backend",
            BACKEND_RSYNC_FILTERS,
        ),
        (environment.deploy_dir / "frontend" / "dist", snapshot.directory / "dist", ()),
    ):
        if live.exists():
            rsync(live, copy, filters)
        else:
            # Nothing is live there yet, so rolling back means putting back nothing
            shutil.rmtree(copy, ignore_errors=True)
            copy.mkdir(parents=True)
    units = snapshot.directory / "systemd"
    shutil.rmtree(units, ignore_errors=True)
    units.mkdir()
    for name in units_for(environment):
        installed = config_home() / "systemd" / "user" / name
        if installed.exists():
            shutil.copy2(installed, units / name)
            snapshot.units.append(name)
    return snapshot


def set_app_version(environment: Environment, version: str) -> None:
    """
    Set ``APP_VERSION`` in the environment's ``.env``, leaving the rest alone.

    :param environment: The environment
    :type environment: Environment
    :param version: The release tag or commit SHA
    :type version: str
    :returns: None
    :rtype: None
    """
    path = env_file(environment)
    lines = path.read_text().splitlines() if path.exists() else []
    replaced = False
    for index, line in enumerate(lines):
        if line.strip().upper().startswith("APP_VERSION="):
            lines[index] = f"APP_VERSION={version}"
            replaced = True
    if not replaced:
        lines.append(f"APP_VERSION={version}")
    write_atomically(path, "\n".join(lines) + "\n", mode=0o600)


def install_python_packages(environment: Environment) -> None:
    """
    Install the backend's dependencies into its virtualenv.

    :param environment: The environment
    :type environment: Environment
    :returns: None
    :rtype: None
    """
    backend = environment.deploy_dir / "backend"
    run(["python3", "-m", "venv", "venv"], cwd=backend)
    run(["venv/bin/pip", "install", "--quiet", "--upgrade", "pip"], cwd=backend)
    run(["venv/bin/pip", "install", "--quiet", "-r", "requirements.txt"], cwd=backend)


def wait_until_healthy(environment: Environment) -> None:
    """
    Wait for the backend to be running and answering ``/health``.

    :param environment: The environment
    :type environment: Environment
    :returns: None
    :rtype: None
    :raises RuntimeError: If it isn't healthy within ``HEALTH_WAIT_SECONDS``
    """
    url = f"http://127.0.0.1:{environment.backend_port}/health"
    deadline = time.monotonic() + HEALTH_WAIT_SECONDS
    while time.monotonic() < deadline:
        active = (
            subprocess.run(
                ["systemctl", "--user", "is-active", "--quiet", environment.backend_service]
            ).returncode
            == 0
        )
        if active:
            try:
                with urllib.request.urlopen(url, timeout=5) as response:
                    if response.status == 200:
                        logger.info("The backend is healthy")
                        return
            except (urllib.error.URLError, OSError):
                pass
        time.sleep(2)
    subprocess.run(
        ["systemctl", "--user", "status", "--no-pager", environment.backend_service]
    )
    raise RuntimeError(
        f"{environment.backend_service} wasn't healthy within {HEALTH_WAIT_SECONDS} seconds"
    )


def systemctl(*arguments: str) -> None:
    """
    Run ``systemctl --user``.

    :param arguments: Its arguments
    :type arguments: str
    :returns: None
    :rtype: None
    """
    run(["systemctl", "--user", *arguments])


def install(source: Path, environment: Environment, version: str) -> None:
    """
    Put the new code in place and restart the backend.

    :param source: The build directory
    :type source: Path
    :param environment: The environment
    :type environment: Environment
    :param version: The release tag or commit SHA
    :type version: str
    :returns: None
    :rtype: None
    """
    backend = environment.deploy_dir / "backend"
    rsync(source / "backend", backend, BACKEND_RSYNC_FILTERS)
    (backend / "data").mkdir(exist_ok=True)
    rsync(source / "frontend" / "dist", environment.deploy_dir / "frontend" / "dist")
    install_python_packages(environment)
    run(["venv/bin/alembic", "upgrade", "head"], cwd=backend)
    set_app_version(environment, version)
    units = config_home() / "systemd" / "user"
    units.mkdir(parents=True, exist_ok=True)
    for name in units_for(environment):
        shutil.copy2(source / "systemd" / name, units / name)
    systemctl("daemon-reload")
    systemctl("enable", environment.backend_service)
    systemctl("enable", "--now", f"staff-app-deploy-{environment.name}.timer")
    systemctl("restart", environment.backend_service)
    wait_until_healthy(environment)


def rollback(
    environment: Environment, snapshot: Snapshot, backup: Path | None, previous: str
) -> str:
    """
    Put back what production had live before this deploy.

    :param environment: The environment
    :type environment: Environment
    :param snapshot: The copy taken before the deploy
    :type snapshot: Snapshot
    :param backup: The database backup taken before the deploy, if there was a
        database
    :type backup: Path | None
    :param previous: The version that was live
    :type previous: str
    :returns: A sentence saying how the rollback went, for the failure email
    :rtype: str
    """
    logger.warning("Rolling production back to %s", previous)
    try:
        subprocess.run(["systemctl", "--user", "stop", environment.backend_service])
        if backup:
            database = backup.parent / "staff-app.db"
            for leftover in ("-journal", "-wal", "-shm"):
                database.with_name(database.name + leftover).unlink(missing_ok=True)
            shutil.copy2(backup, database)
        backend = environment.deploy_dir / "backend"
        rsync(snapshot.directory / "backend", backend, BACKEND_RSYNC_FILTERS)
        rsync(snapshot.directory / "dist", environment.deploy_dir / "frontend" / "dist")
        install_python_packages(environment)
        set_app_version(environment, previous)
        units = config_home() / "systemd" / "user"
        for name in snapshot.units:
            shutil.copy2(snapshot.directory / "systemd" / name, units / name)
        systemctl("daemon-reload")
        systemctl("start", environment.backend_service)
        wait_until_healthy(environment)
    except (
        Exception
    ) as error:  # noqa: BLE001 - any failure here means production may be down
        logger.exception("The rollback failed")
        return (
            f"Rolling back to {previous} also failed ({error}), so production may be down."
        )
    return f"Production was rolled back to {previous} and is up."


def finish(source: Path, environment: Environment, version: str) -> None:
    """
    Record the new version, update the stable scripts, and say so.

    :param source: The build directory
    :type source: Path
    :param environment: The environment
    :type environment: Environment
    :param version: The release tag or commit SHA now live
    :type version: str
    :returns: None
    :rtype: None
    """
    write_atomically(environment.deploy_dir / "DEPLOYED_VERSION", version + "\n")
    for name in STABLE_FILES:
        write_atomically(
            environment.stable_dir / name,
            (source / "deploy" / name).read_text(),
            mode=0o755,
        )
    logger.info("Deployed %s to %s", version, environment.name)
    if environment.name == "production":
        send_email(
            environment,
            f"[KALX Staff App] {version} deployed to production",
            f"{version} is now live in production.\n",
        )


def main(argv: Sequence[str] | None = None) -> int:
    """
    Install this code into an environment.

    :param argv: The arguments, or None for ``sys.argv``
    :type argv: Sequence[str] | None
    :returns: The exit status
    :rtype: int
    """
    args = parse_args(argv)
    setup_logging(args.verbose)
    environment = get_environment(args.environment)
    source = Path(__file__).resolve().parent.parent
    production = environment.name == "production"
    try:
        build_frontend(source, environment, args.version)
        os.chmod(Path.home(), 0o755)  # Apache serves frontend/dist from here
        backup = backup_database(environment)
        snapshot = take_snapshot(environment) if production else None
    except Exception as error:  # noqa: BLE001 - reported in the failure email
        logger.exception("Getting %s ready failed", args.version)
        record_failure(
            environment,
            f"Getting {args.version} ready for {environment.name} (building the "
            "frontend, backing up the database or copying what's live) failed, so "
            f"nothing was changed and {args.previous} is still live: {error}",
        )
        return 1
    try:
        install(source, environment, args.version)
    except Exception as error:  # noqa: BLE001 - reported in the failure email
        logger.exception("Installing %s failed", args.version)
        if snapshot is None:
            record_failure(
                environment,
                f"Installing {args.version} on {environment.name} failed ({error}). "
                f"It was left as it is, and it isn't retried until main changes.",
            )
        else:
            outcome = rollback(environment, snapshot, backup, args.previous)
            record_failure(
                environment,
                f"Installing {args.version} on production failed ({error}). {outcome} "
                "The next nightly run tries the release again.",
            )
        return 1
    finish(source, environment, args.version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
