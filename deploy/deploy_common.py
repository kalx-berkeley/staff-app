"""
Code shared by the KALX Staff App's server-side deploy scripts.

The deploy scripts run on the server with the system ``python3`` and only the
standard library, because they build the backend's virtualenv rather than run
inside it. The design is in docs/deployment/specs/server-side-deploy/plan.md.
"""

from __future__ import annotations

import contextlib
import datetime
import fcntl
import hashlib
import json
import logging
import os
import smtplib
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Any

logger = logging.getLogger("staff-app-deploy")

GITHUB_API = "https://api.github.com"
USER_AGENT = "kalx-staff-app-deploy"
# The check runs (CI job names) a commit needs to have passed to be deployed
REQUIRED_CHECKS = ("Run Backend Tests", "Run Frontend Tests")
# A failure email with the same reason as the last one waits this long, so a
# problem that repeats doesn't send an email on every run
FAILURE_EMAIL_REPEAT_AFTER = datetime.timedelta(hours=12)
DEFAULT_FROM_ADDRESS = "noreply@kalx.berkeley.edu"
# rsync filter rules for the backend: files the deploy never deletes or
# overwrites in the deploy directory, then caches it doesn't copy. The caches
# are "perishable" (-p), so a folder holding nothing but caches, such as one
# left over after the code moved, is deleted rather than kept for them.
BACKEND_RSYNC_FILTERS = (
    "- venv",
    "- data",
    "- .env",
    "- test*.db",
    "-p __pycache__/",
    "-p .pytest_cache/",
    "-p *.pyc",
    "-p .coverage",
)


class DeployFailed(Exception):
    """A deploy stopped for a reason worth emailing about."""


class GitHubUnavailable(Exception):
    """GitHub couldn't be reached or didn't answer usefully."""


@dataclass(frozen=True)
class Environment:
    """Where one environment (staging or production) lives on the server."""

    name: str
    backend_service: str
    backend_port: int
    deploy_dir: Path
    build_dir: Path
    snapshot_dir: Path
    stable_dir: Path
    state_dir: Path


BACKEND_SERVICES = {
    "staging": ("staff-app-backend-staging", 8421),
    "production": ("staff-app-backend-production", 8420),
}


def get_environment(name: str) -> Environment:
    """
    Describe an environment, with paths under the current home directory.

    :param name: ``staging`` or ``production``
    :type name: str
    :returns: The environment's services and paths
    :rtype: Environment
    """
    service, port = BACKEND_SERVICES[name]
    home = Path.home()
    return Environment(
        name=name,
        backend_service=service,
        backend_port=port,
        deploy_dir=home / f"staff-app-{name}",
        build_dir=home / "staff-app-build" / name,
        snapshot_dir=home / "staff-app-build" / f"{name}-previous",
        stable_dir=home / "staff-app-deploy" / name,
        state_dir=home / "staff-app-deploy" / "state" / name,
    )


def config_home() -> Path:
    """
    The XDG config directory, which holds the GitHub token and systemd units.

    :returns: ``$XDG_CONFIG_HOME``, or ``~/.config`` when it isn't set
    :rtype: Path
    """
    configured = os.environ.get("XDG_CONFIG_HOME")
    return Path(configured) if configured else Path.home() / ".config"


def source_repo() -> Path:
    """
    The git clone the deploys fetch code into.

    :returns: ``~/staff-app-src``
    :rtype: Path
    """
    return Path.home() / "staff-app-src"


def setup_logging(verbose: bool) -> None:
    """
    Log to stdout, which systemd sends to the journal.

    :param verbose: Whether to include debug messages, such as runs that find
        nothing to deploy
    :type verbose: bool
    :returns: None
    :rtype: None
    """
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )


def run(
    command: Sequence[str | Path],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    capture: bool = False,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """
    Run a command, raising if it fails.

    :param command: The command and its arguments
    :type command: Sequence[str | Path]
    :param cwd: The directory to run it in
    :type cwd: Path | None
    :param env: The environment, or None for this process's
    :type env: dict[str, str] | None
    :param capture: Whether to return its output instead of letting it through
    :type capture: bool
    :param timeout: Seconds to wait before giving up, or None to wait forever
    :type timeout: float | None
    :returns: The finished process
    :rtype: subprocess.CompletedProcess[str]
    """
    logger.debug("Running %s", " ".join(str(part) for part in command))
    return subprocess.run(
        [str(part) for part in command],
        cwd=cwd,
        env=env,
        check=True,
        text=True,
        capture_output=capture,
        timeout=timeout,
    )


@contextlib.contextmanager
def locked(path: Path, wait: bool = False) -> Iterator[bool]:
    """
    Hold an exclusive lock on a file.

    :param path: The lock file, created if it's missing
    :type path: Path
    :param wait: Whether to wait for the lock, rather than give up at once
    :type wait: bool
    :returns: A context that yields whether the lock was acquired
    :rtype: Iterator[bool]
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX if wait else fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def write_atomically(path: Path, text: str, mode: int | None = None) -> None:
    """
    Replace a file's contents in one step, so a reader never sees half of it.

    Replacing (rather than rewriting) also keeps a running script safe, since
    the old file stays open under its old inode.

    :param path: The file to write
    :type path: Path
    :param text: Its new contents
    :type text: str
    :param mode: Permissions for the file, or None to keep the current ones
        (or the default for a new file)
    :type mode: int | None
    :returns: None
    :rtype: None
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode is None and path.exists():
        mode = path.stat().st_mode & 0o7777
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text)
    if mode is not None:
        temporary.chmod(mode)
    temporary.replace(path)


def read_env_file(path: Path) -> dict[str, str]:
    """
    Read a backend ``.env`` file's settings.

    :param path: The ``.env`` file
    :type path: Path
    :returns: Each setting, with its name upper-cased (the backend reads names
        case-insensitively), or nothing if the file is missing
    :rtype: dict[str, str]
    """
    settings: dict[str, str] = {}
    if not path.exists():
        return settings
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        settings[name.strip().upper()] = value
    return settings


def env_file(environment: Environment) -> Path:
    """
    The environment's backend settings file.

    :param environment: The environment
    :type environment: Environment
    :returns: ``~/staff-app-<environment>/backend/.env``
    :rtype: Path
    """
    return environment.deploy_dir / "backend" / ".env"


def read_state(environment: Environment, name: str) -> str | None:
    """
    Read one of the environment's deploy state files.

    :param environment: The environment
    :type environment: Environment
    :param name: The state file's name
    :type name: str
    :returns: Its contents without surrounding whitespace, or None if it's
        missing or empty
    :rtype: str | None
    """
    path = environment.state_dir / name
    if not path.exists():
        return None
    return path.read_text().strip() or None


def write_state(environment: Environment, name: str, value: str | None) -> None:
    """
    Write one of the environment's deploy state files.

    :param environment: The environment
    :type environment: Environment
    :param name: The state file's name
    :type name: str
    :param value: What to store, or None to remove the file
    :type value: str | None
    :returns: None
    :rtype: None
    """
    path = environment.state_dir / name
    if value is None:
        path.unlink(missing_ok=True)
    else:
        write_atomically(path, value + "\n")


def record_failure(environment: Environment, reason: str) -> None:
    """
    Save why a deploy failed, for the failure email to quote.

    :param environment: The environment
    :type environment: Environment
    :param reason: What went wrong, in a sentence or two
    :type reason: str
    :returns: None
    :rtype: None
    """
    logger.error("%s", reason)
    write_state(environment, "last-failure", reason)


def repo_slug() -> str:
    """
    The GitHub ``owner/repo`` that the source clone fetches from.

    :returns: For example ``kalx-berkeley/staff-app``
    :rtype: str
    """
    url = run(
        ["git", "-C", source_repo(), "remote", "get-url", "origin"], capture=True
    ).stdout.strip()
    path = url.split("github.com", 1)[-1].lstrip(":/")
    return path.removesuffix(".git")


def github_token() -> str | None:
    """
    Read the server's read-only GitHub token.

    :returns: The token, or None if there's no token file
    :rtype: str | None
    """
    path = config_home() / "staff-app-deploy" / "github-token"
    if not path.exists():
        return None
    return path.read_text().strip() or None


def _github_request(url: str, token: str | None) -> Any:
    """
    Make one GitHub API request.

    :param url: The full API URL
    :type url: str
    :param token: The token to send, or None to send none
    :type token: str | None
    :returns: The decoded JSON answer
    :rtype: Any
    """
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": USER_AGENT,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def github_json(environment: Environment, path: str) -> Any:
    """
    Fetch from GitHub's API, with the token when there is one.

    When GitHub rejects the token, the request is made again without it, so
    deploys carry on, and an email (at most once a day) says to replace it.

    :param environment: The environment, whose ``.env`` says where that
        email goes
    :type environment: Environment
    :param path: The API path, such as ``/repos/owner/repo/releases/latest``
    :type path: str
    :returns: The decoded JSON answer
    :rtype: Any
    :raises GitHubUnavailable: If GitHub can't be reached or refuses
    """
    url = GITHUB_API + path
    token = github_token()
    try:
        try:
            return _github_request(url, token)
        except urllib.error.HTTPError as error:
            if error.code != 401 or not token:
                raise
            logger.warning("GitHub rejected the token, so this request was made without it")
            warn_about_token(environment)
            return _github_request(url, None)
    except urllib.error.HTTPError as error:
        raise GitHubUnavailable(f"GitHub answered {path} with HTTP {error.code}") from error
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
        raise GitHubUnavailable(f"couldn't reach GitHub for {path}: {error}") from error


def warn_about_token(environment: Environment) -> None:
    """
    Email that GitHub rejected the token, at most once a day.

    :param environment: The environment whose ``.env`` says where the email goes
    :type environment: Environment
    :returns: None
    :rtype: None
    """
    marker = Path.home() / "staff-app-deploy" / "state" / "token-warned"
    today = datetime.date.today().isoformat()
    if marker.exists() and marker.read_text().strip() == today:
        return
    token_path = config_home() / "staff-app-deploy" / "github-token"
    sent = send_email(
        environment,
        "[KALX Staff App] The deploy's GitHub token needs replacing",
        "GitHub rejected the server's GitHub token, probably because it expired "
        "or was revoked. Deploys carry on without it, but GitHub allows only 60 "
        "requests an hour without one.\n\n"
        "Make a new fine-grained token with Repository access: Public "
        "repositories (read-only) and no permissions added, then save it on the "
        f"server as {token_path} (mode 600).\n",
    )
    if sent:
        write_atomically(marker, today + "\n")


def send_email(environment: Environment, subject: str, body: str) -> bool:
    """
    Email the webmaster through the server's local SMTP relay.

    This deliberately doesn't use the app's own email code, which may be what
    a failed deploy broke.

    :param environment: The environment, whose ``.env`` has ``WEBMASTER_EMAIL``
        and the relay's settings
    :type environment: Environment
    :param subject: The subject line
    :type subject: str
    :param body: The plain-text body
    :type body: str
    :returns: Whether the email was sent
    :rtype: bool
    """
    settings = read_env_file(env_file(environment))
    recipient = settings.get("WEBMASTER_EMAIL")
    if not recipient:
        logger.warning("WEBMASTER_EMAIL isn't set, so this email wasn't sent: %s", subject)
        return False
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.get("EMAIL_FROM_ADDRESS") or DEFAULT_FROM_ADDRESS
    message["To"] = recipient
    message.set_content(body)
    host = settings.get("LOCAL_SMTP_HOST") or "localhost"
    port = int(settings.get("LOCAL_SMTP_PORT") or 25)
    try:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as error:
        logger.error(
            "Couldn't send the email %r through %s:%s: %s", subject, host, port, error
        )
        return False
    logger.info("Emailed %s: %s", recipient, subject)
    return True


def send_failure_email(environment: Environment, reason: str, log: str) -> bool:
    """
    Email that a deploy failed, unless the same failure was emailed recently.

    :param environment: The environment
    :type environment: Environment
    :param reason: Why it failed
    :type reason: str
    :param log: The end of the deploy's log, to include
    :type log: str
    :returns: Whether an email was sent
    :rtype: bool
    """
    key = hashlib.sha256(reason.encode()).hexdigest()
    now = datetime.datetime.now(datetime.timezone.utc)
    previous = read_state(environment, "last-failure-email")
    if previous:
        try:
            last = json.loads(previous)
            sent_at = datetime.datetime.fromisoformat(last["sent_at"])
            if last["key"] == key and now - sent_at < FAILURE_EMAIL_REPEAT_AFTER:
                logger.info(
                    "This failure was emailed at %s, so it isn't emailed again", sent_at
                )
                return False
        except (ValueError, KeyError, TypeError):
            pass
    sent = send_email(
        environment,
        f"[KALX Staff App] The {environment.name} deploy failed",
        f"{reason}\n\n"
        f"To see the whole log on the server, run:\n"
        f"  journalctl --user -u staff-app-deploy@{environment.name}\n\n"
        f"The end of the log:\n\n{log}\n",
    )
    if sent:
        write_state(
            environment,
            "last-failure-email",
            json.dumps({"key": key, "sent_at": now.isoformat()}),
        )
    return sent
