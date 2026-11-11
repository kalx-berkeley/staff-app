#!/usr/bin/env python3
"""
Decide whether an environment has something to deploy, fetch it, and install it.

systemd runs this from a stable copy, ``~/staff-app-deploy/<environment>/``:
``staff-app-deploy-staging.timer`` every 2 minutes, and
``staff-app-deploy-production.timer`` at 3:51am Pacific. It can also be run by
hand. It works out the target (the newest commit on ``main`` for staging, the
newest release for production), checks it's new and that CI passed, then
fetches it into a build directory and runs that code's ``deploy/install.py``.

Runs that find nothing to deploy log nothing, because staging runs every 2
minutes. Failures worth emailing exit with status 1 after saving their reason,
and the ``OnFailure=`` unit emails it.
"""

from __future__ import annotations

import argparse
import logging
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence

from deploy_common import (
    REQUIRED_CHECKS,
    DeployFailed,
    Environment,
    GitHubUnavailable,
    env_file,
    get_environment,
    github_json,
    locked,
    read_env_file,
    read_state,
    record_failure,
    repo_slug,
    run,
    setup_logging,
    source_repo,
    write_atomically,
    write_state,
)

logger = logging.getLogger("staff-app-deploy")

VERSION_TAG = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """
    Read the command line.

    :param argv: The arguments, or None for ``sys.argv``
    :type argv: Sequence[str] | None
    :returns: The parsed arguments
    :rtype: argparse.Namespace
    """
    parser = argparse.ArgumentParser(
        description="Deploy the newest commit (staging) or release (production) "
        "of the KALX Staff App, if it isn't live yet."
    )
    parser.add_argument("environment", choices=["staging", "production"])
    parser.add_argument(
        "--ref",
        help="deploy this release tag or commit instead of the newest one",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="deploy even if the target is already live, an older release, "
        "or a staging commit whose deploy failed",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="say what would be deployed, without changing anything",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="also log runs with nothing to do"
    )
    return parser.parse_args(argv)


def deployed_version(environment: Environment, dry_run: bool) -> str:
    """
    Read what the environment has live.

    The first time, before ``DEPLOYED_VERSION`` exists, it starts from the
    ``APP_VERSION`` that the old GitHub Actions deploy wrote into ``.env``.

    :param environment: The environment
    :type environment: Environment
    :param dry_run: Whether to leave a missing ``DEPLOYED_VERSION`` unwritten
    :type dry_run: bool
    :returns: The live release tag (production) or commit SHA (staging)
    :rtype: str
    :raises DeployFailed: If neither file says what's live
    """
    path = environment.deploy_dir / "DEPLOYED_VERSION"
    if path.exists() and path.read_text().strip():
        return path.read_text().strip()
    app_version = read_env_file(env_file(environment)).get("APP_VERSION", "")
    if not app_version or app_version == "None":
        raise DeployFailed(
            f"Nothing says what {environment.name} has live: {path} is missing and "
            f"{env_file(environment)} has no APP_VERSION. Write the live version "
            f"into {path} (a release tag for production, a commit SHA for "
            "staging), and deploys will start again."
        )
    if not dry_run:
        write_atomically(path, app_version + "\n")
        logger.info("Started %s from APP_VERSION: %s", path, app_version)
    return app_version


def git_network(arguments: Sequence[str]) -> str:
    """
    Run a git command that talks to GitHub, in the source clone.

    :param arguments: The git arguments
    :type arguments: Sequence[str]
    :returns: Its output
    :rtype: str
    :raises GitHubUnavailable: If it fails
    """
    try:
        return run(
            ["git", "-C", source_repo(), *arguments], capture=True, timeout=300
        ).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        output = " ".join(
            (getattr(error, stream, "") or "").strip() for stream in ("stderr", "stdout")
        ).strip()
        raise GitHubUnavailable(f"git {arguments[0]} failed: {output or error}") from error


def resolve_commit(ref: str) -> str:
    """
    Fetch from GitHub and find the commit a tag, branch or SHA points at.

    :param ref: A release tag, ``main``, or a commit SHA
    :type ref: str
    :returns: The full commit SHA
    :rtype: str
    :raises GitHubUnavailable: If fetching fails
    :raises DeployFailed: If the ref doesn't exist
    """
    # --force lets a release tag that was deleted and made again update here too
    git_network(
        ["fetch", "--quiet", "--prune", "--prune-tags", "--force", "--tags", "origin"]
    )
    for candidate in (f"refs/tags/{ref}", f"refs/remotes/origin/{ref}", ref):
        result = subprocess.run(
            [
                "git",
                "-C",
                str(source_repo()),
                "rev-parse",
                "--verify",
                "--quiet",
                f"{candidate}^{{commit}}",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    raise DeployFailed(f"{ref} isn't a tag, branch or commit in the repository")


def choose_target(environment: Environment, ref: str | None) -> tuple[str, str]:
    """
    Work out what the environment should be running.

    :param environment: The environment
    :type environment: Environment
    :param ref: A tag or commit to deploy instead of the newest, or None
    :type ref: str | None
    :returns: The version to deploy (a release tag for production, a commit SHA
        for staging) and its commit SHA
    :rtype: tuple[str, str]
    :raises GitHubUnavailable: If GitHub can't be reached
    """
    if ref:
        sha = resolve_commit(ref)
        return (ref if environment.name == "production" else sha), sha
    if environment.name == "staging":
        output = git_network(["ls-remote", "origin", "refs/heads/main"])
        if not output.strip():
            raise GitHubUnavailable("git ls-remote found no main branch")
        sha = output.split()[0]
        return sha, sha
    release = github_json(environment, f"/repos/{repo_slug()}/releases/latest")
    tag = release["tag_name"]
    return tag, resolve_commit(tag)


def is_older_release(target: str, deployed: str) -> bool:
    """
    Whether a release tag is older than the one that's live.

    :param target: The release to deploy, such as ``v1.12.2``
    :type target: str
    :param deployed: The live release, such as ``v1.13.0``
    :type deployed: str
    :returns: True only when both are version tags and the target is lower
    :rtype: bool
    """
    target_match = VERSION_TAG.match(target)
    deployed_match = VERSION_TAG.match(deployed)
    if not target_match or not deployed_match:
        return False
    return tuple(map(int, target_match.groups())) < tuple(map(int, deployed_match.groups()))


def ci_status(environment: Environment, sha: str) -> str:
    """
    Whether CI passed for a commit.

    :param environment: The environment
    :type environment: Environment
    :param sha: The commit
    :type sha: str
    :returns: ``passed`` when every required check succeeded, ``failed`` when
        any finished another way, ``missing`` when none of them has started
        (CI never ran for the commit, or GitHub hasn't queued it yet), otherwise
        ``pending``
    :rtype: str
    :raises GitHubUnavailable: If GitHub can't be reached
    """
    answer = github_json(
        environment, f"/repos/{repo_slug()}/commits/{sha}/check-runs?per_page=100"
    )
    latest: dict[str, dict] = {}
    for check in answer.get("check_runs", []):
        name = check.get("name")
        if name in REQUIRED_CHECKS and check.get("id", 0) >= latest.get(name, {}).get(
            "id", -1
        ):
            latest[name] = check
    if any(
        check.get("status") == "completed" and check.get("conclusion") != "success"
        for check in latest.values()
    ):
        return "failed"
    if len(latest) == len(REQUIRED_CHECKS) and all(
        check.get("conclusion") == "success" for check in latest.values()
    ):
        return "passed"
    return "pending" if latest else "missing"


def check_ci(environment: Environment, version: str, sha: str, dry_run: bool) -> bool:
    """
    Decide from CI whether to go ahead with the deploy.

    Staging remembers each commit's settled result, so it asks GitHub again
    only while CI is still running.

    :param environment: The environment
    :type environment: Environment
    :param version: The version being deployed
    :type version: str
    :param sha: Its commit
    :type sha: str
    :param dry_run: Whether to leave staging's remembered result alone
    :type dry_run: bool
    :returns: Whether CI passed
    :rtype: bool
    :raises DeployFailed: If a production release's CI failed
    """
    if environment.name == "staging":
        if read_state(environment, "checked") == f"{sha} failed":
            logger.debug("%s's CI failed earlier, so staging stays as it is", sha)
            return False
        status = ci_status(environment, sha)
        if not dry_run:
            write_state(environment, "checked", f"{sha} {status}")
        if status in ("pending", "missing"):
            # Right after a push, the checks may not have been queued yet
            logger.debug("CI hasn't finished for %s yet", sha)
        elif status == "failed":
            logger.info("CI failed for %s, so staging stays as it is", sha)
        return status == "passed"
    status = ci_status(environment, sha)
    if status == "failed":
        raise DeployFailed(
            f"The tests failed for {version}, so it wasn't deployed to production. "
            "Publish a release whose tests pass, and the next nightly run deploys it."
        )
    if status == "missing":
        raise DeployFailed(
            f"The tests never ran for {version}'s commit ({sha[:7]}), so it can't be "
            "deployed to production. This happens to a release whose commit only "
            "changed files CI used to skip, such as CHANGELOG.md. Publish a new "
            "release from a commit whose Run Backend Tests and Run Frontend Tests "
            "checks passed, and the next nightly run deploys it."
        )
    if status == "pending":
        logger.info(
            "CI hasn't finished for %s, so it deploys on the next nightly run", version
        )
    return status == "passed"


def fetch_code(sha: str, environment: Environment) -> None:
    """
    Put a clean copy of a commit's files in the environment's build directory.

    :param sha: The commit
    :type sha: str
    :param environment: The environment
    :type environment: Environment
    :returns: None
    :rtype: None
    """
    shutil.rmtree(environment.build_dir, ignore_errors=True)
    environment.build_dir.mkdir(parents=True)
    archive = subprocess.Popen(
        ["git", "-C", str(source_repo()), "archive", "--format=tar", sha],
        stdout=subprocess.PIPE,
    )
    extract = subprocess.run(
        ["tar", "-x", "-C", str(environment.build_dir)], stdin=archive.stdout
    )
    archive.stdout.close()
    if archive.wait() != 0 or extract.returncode != 0:
        raise DeployFailed(f"Couldn't copy the code for {sha} into {environment.build_dir}")


def run_install(
    environment: Environment, version: str, deployed: str, verbose: bool
) -> bool:
    """
    Run the fetched code's ``deploy/install.py``.

    :param environment: The environment
    :type environment: Environment
    :param version: The version being deployed
    :type version: str
    :param deployed: The version live now, for production to roll back to
    :type deployed: str
    :param verbose: Whether to pass ``--verbose`` on
    :type verbose: bool
    :returns: Whether it succeeded
    :rtype: bool
    """
    command = [
        sys.executable,
        str(environment.build_dir / "deploy" / "install.py"),
        environment.name,
        "--version",
        version,
        "--previous",
        deployed,
    ]
    if verbose:
        command.append("--verbose")
    return subprocess.run(command).returncode == 0


def deploy(environment: Environment, args: argparse.Namespace) -> int:
    """
    Deploy the environment's target if it should be deployed.

    :param environment: The environment
    :type environment: Environment
    :param args: The command line
    :type args: argparse.Namespace
    :returns: The exit status: 0 when deployed or nothing to do, 1 on failure
    :rtype: int
    :raises DeployFailed: For failures worth emailing
    """
    production = environment.name == "production"
    if not args.dry_run:
        write_state(environment, "last-failure", None)
    deployed = deployed_version(environment, args.dry_run)
    try:
        version, sha = choose_target(environment, args.ref)
        if version == deployed and not args.force:
            logger.debug("%s is already live on %s", version, environment.name)
            return 0
        if (
            not production
            and not args.force
            and read_state(environment, "failed") == version
        ):
            logger.debug("Deploying %s failed before, so it isn't tried again", version)
            return 0
        if production and not args.force and is_older_release(version, deployed):
            raise DeployFailed(
                f"The release marked Latest, {version}, is older than the live "
                f"{deployed}, so it wasn't deployed: an older release may not work "
                "with the newer database. To go back on purpose, run "
                f"~/staff-app-deploy/production/fetch.py production --ref {version} --force"
            )
        if not check_ci(environment, version, sha, args.dry_run):
            return 0
    except GitHubUnavailable as error:
        if production:
            raise DeployFailed(
                f"The production deploy couldn't check GitHub for a new release, so "
                f"nothing was deployed: {error}"
            ) from error
        logger.debug(
            "Couldn't reach GitHub, so staging tries again on the next run: %s", error
        )
        return 0

    if args.dry_run:
        logger.info(
            "Would deploy %s (%s) to %s, replacing %s",
            version,
            sha,
            environment.name,
            deployed,
        )
        return 0
    logger.info(
        "Deploying %s (%s) to %s, replacing %s", version, sha, environment.name, deployed
    )
    fetch_code(sha, environment)
    if not run_install(environment, version, deployed, args.verbose):
        if not production:
            write_state(environment, "failed", version)
        if not read_state(environment, "last-failure"):
            record_failure(
                environment,
                f"Installing {version} on {environment.name} failed. See the log.",
            )
        return 1
    write_state(environment, "failed", None)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """
    Run a deploy, holding the environment's lock so two never overlap.

    :param argv: The arguments, or None for ``sys.argv``
    :type argv: Sequence[str] | None
    :returns: The exit status
    :rtype: int
    """
    args = parse_args(argv)
    setup_logging(args.verbose)
    environment = get_environment(args.environment)
    with locked(environment.state_dir / "lock") as acquired:
        if not acquired:
            logger.info(
                "Another %s deploy is running, so this one stopped", environment.name
            )
            return 0
        try:
            return deploy(environment, args)
        except DeployFailed as error:
            record_failure(environment, str(error))
            return 1


if __name__ == "__main__":
    sys.exit(main())
