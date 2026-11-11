"""Tests for fetch.py: deciding whether there's something to deploy."""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import pytest

import fetch
from conftest import write_env
from deploy_common import GitHubUnavailable, get_environment, read_state

STAGING_LIVE = "a" * 40
STAGING_NEW = "b" * 40
RELEASE_SHA = "c" * 40


@dataclass
class FakeServer:
    """Stands in for GitHub, git and install.py."""

    main: str = STAGING_NEW
    latest_release: str = "v1.14.0"
    # Each commit's check runs, as GitHub's API lists them
    checks: dict[str, list[dict]] = field(default_factory=dict)
    unavailable: bool = False
    install_succeeds: bool = True
    installs: list[tuple[str, str, str]] = field(default_factory=list)
    api_calls: list[str] = field(default_factory=list)

    def git_network(self, arguments: list[str]) -> str:
        if self.unavailable:
            raise GitHubUnavailable("no network")
        return f"{self.main}\trefs/heads/main\n"

    def github_json(self, environment: object, path: str) -> dict:
        self.api_calls.append(path)
        if self.unavailable:
            raise GitHubUnavailable("no network")
        if path.endswith("/releases/latest"):
            return {"tag_name": self.latest_release}
        sha = path.split("/commits/")[1].split("/")[0]
        return {"check_runs": self.checks.get(sha, [])}

    def resolve_commit(self, ref: str) -> str:
        if self.unavailable:
            raise GitHubUnavailable("no network")
        return RELEASE_SHA if ref.startswith("v") else ref

    def run_install(self, environment, version: str, deployed: str, verbose: bool) -> bool:
        self.installs.append((environment.name, version, deployed))
        if not self.install_succeeds:
            # install.py records its own reason before failing
            (environment.state_dir / "last-failure").write_text("install broke\n")
        return self.install_succeeds


def passing(sha_checks: str = "success") -> list[dict]:
    """Check runs for both required jobs, with one conclusion."""
    return [
        {
            "id": 1,
            "name": "Run Backend Tests",
            "status": "completed",
            "conclusion": sha_checks,
        },
        {
            "id": 2,
            "name": "Run Frontend Tests",
            "status": "completed",
            "conclusion": "success",
        },
    ]


@pytest.fixture
def server(home: Path, monkeypatch: pytest.MonkeyPatch) -> FakeServer:
    fake = FakeServer()
    for name in ("git_network", "github_json", "resolve_commit", "run_install"):
        monkeypatch.setattr(fetch, name, getattr(fake, name))
    monkeypatch.setattr(fetch, "repo_slug", lambda: "kalx-berkeley/staff-app")
    monkeypatch.setattr(fetch, "fetch_code", lambda sha, environment: None)
    for environment, live in (("staging", STAGING_LIVE), ("production", "v1.13.1")):
        write_env(
            home, environment, f"WEBMASTER_EMAIL=web@example.com\nAPP_VERSION={live}\n"
        )
    return fake


def deploy(*argv: str) -> int:
    return fetch.main(list(argv))


def test_staging_with_nothing_new_logs_nothing(server, caplog):
    server.main = STAGING_LIVE
    with caplog.at_level(logging.INFO, logger="staff-app-deploy"):
        assert deploy("staging") == 0
    assert server.installs == [] and server.api_calls == []
    assert [r for r in caplog.records if "Started" not in r.getMessage()] == []


def test_staging_waits_quietly_while_ci_runs(server, caplog):
    with caplog.at_level(logging.INFO, logger="staff-app-deploy"):
        assert deploy("staging") == 0
    assert server.installs == []
    assert read_state(get_environment("staging"), "checked") == f"{STAGING_NEW} pending"
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_staging_deploys_once_ci_passes(server):
    deploy("staging")
    server.checks[STAGING_NEW] = passing()
    assert deploy("staging") == 0
    assert server.installs == [("staging", STAGING_NEW, STAGING_LIVE)]


def test_staging_stops_asking_github_about_a_failed_commit(server):
    server.checks[STAGING_NEW] = passing("failure")
    assert deploy("staging") == 0
    assert deploy("staging") == 0
    assert server.installs == []
    assert len(server.api_calls) == 1


def test_a_rerun_after_a_failure_counts(server):
    server.checks[STAGING_NEW] = passing("failure") + [
        {
            "id": 3,
            "name": "Run Backend Tests",
            "status": "completed",
            "conclusion": "success",
        }
    ]
    assert deploy("staging") == 0
    assert server.installs == [("staging", STAGING_NEW, STAGING_LIVE)]


def test_a_missing_check_is_still_pending(server):
    server.checks[STAGING_NEW] = passing()[:1]
    assert deploy("staging") == 0
    assert server.installs == []


def test_a_failed_staging_deploy_isnt_retried_until_main_moves(server):
    server.checks[STAGING_NEW] = passing()
    server.install_succeeds = False
    assert deploy("staging") == 1
    staging = get_environment("staging")
    assert read_state(staging, "failed") == STAGING_NEW
    assert read_state(staging, "last-failure") == "install broke"

    assert deploy("staging") == 0
    assert len(server.installs) == 1

    server.install_succeeds = True
    assert deploy("staging", "--force") == 0
    assert len(server.installs) == 2
    assert read_state(staging, "failed") is None


def test_staging_stays_quiet_when_github_is_down(server):
    server.unavailable = True
    assert deploy("staging") == 0
    assert read_state(get_environment("staging"), "last-failure") is None


def test_production_deploys_a_new_release_whose_ci_passed(server):
    server.checks[RELEASE_SHA] = passing()
    assert deploy("production") == 0
    assert server.installs == [("production", "v1.14.0", "v1.13.1")]


def test_production_waits_for_the_next_night_while_ci_runs(server):
    assert deploy("production") == 0
    assert server.installs == []
    assert read_state(get_environment("production"), "last-failure") is None


def test_production_emails_when_a_release_failed_ci(server):
    server.checks[RELEASE_SHA] = passing("failure")
    assert deploy("production") == 1
    reason = read_state(get_environment("production"), "last-failure")
    assert "v1.14.0" in reason and "tests failed" in reason
    assert server.installs == []


def test_production_refuses_an_older_latest_release(server):
    server.latest_release = "v1.12.2"
    server.checks[RELEASE_SHA] = passing()
    assert deploy("production") == 1
    reason = read_state(get_environment("production"), "last-failure")
    assert "older than the live v1.13.1" in reason
    assert server.installs == []


def test_going_back_a_release_on_purpose(server):
    server.checks[RELEASE_SHA] = passing()
    assert deploy("production", "--ref", "v1.12.2", "--force") == 0
    assert server.installs == [("production", "v1.12.2", "v1.13.1")]


def test_production_emails_when_github_is_down(server):
    server.unavailable = True
    assert deploy("production") == 1
    assert "couldn't check GitHub" in read_state(
        get_environment("production"), "last-failure"
    )


def test_production_retries_a_failed_release(server):
    server.checks[RELEASE_SHA] = passing()
    server.install_succeeds = False
    assert deploy("production") == 1
    server.install_succeeds = True
    assert deploy("production") == 0
    assert len(server.installs) == 2


def test_already_live_needs_force_to_redeploy(server):
    server.latest_release = "v1.13.1"
    server.checks[RELEASE_SHA] = passing()
    assert deploy("production") == 0
    assert server.installs == []
    assert deploy("production", "--force") == 0
    assert server.installs == [("production", "v1.13.1", "v1.13.1")]


def test_deployed_version_starts_from_app_version(server, home):
    server.main = STAGING_LIVE
    deploy("staging")
    assert (
        home / "staff-app-staging" / "DEPLOYED_VERSION"
    ).read_text() == STAGING_LIVE + "\n"


def test_deployed_version_wins_over_app_version(server, home):
    (home / "staff-app-staging" / "DEPLOYED_VERSION").write_text(STAGING_NEW + "\n")
    assert deploy("staging") == 0
    assert server.api_calls == []


def test_unknown_deployed_version_refuses(server, home):
    write_env(home, "production", "WEBMASTER_EMAIL=web@example.com\n")
    server.checks[RELEASE_SHA] = passing()
    assert deploy("production") == 1
    assert "Nothing says what production has live" in read_state(
        get_environment("production"), "last-failure"
    )
    assert server.installs == []


def test_dry_run_changes_nothing(server, home, caplog):
    server.checks[RELEASE_SHA] = passing()
    with caplog.at_level(logging.INFO, logger="staff-app-deploy"):
        assert deploy("production", "--dry-run") == 0
    assert server.installs == []
    assert not (home / "staff-app-production" / "DEPLOYED_VERSION").exists()
    assert "Would deploy v1.14.0" in caplog.text


def test_a_run_while_another_holds_the_lock_stops(server):
    staging = get_environment("staging")
    with fetch.locked(staging.state_dir / "lock") as acquired:
        assert acquired
        server.checks[STAGING_NEW] = passing()
        assert deploy("staging") == 0
    assert server.installs == []


@pytest.mark.parametrize(
    ("target", "deployed", "older"),
    [
        ("v1.12.2", "v1.13.0", True),
        ("v1.13.0", "v1.12.10", False),
        ("v1.13.0", "v1.13.0", False),
        ("v2.0.0", "v1.99.99", False),
        ("v1.13.0-rc1", "v1.14.0", False),
    ],
)
def test_is_older_release(target, deployed, older):
    assert fetch.is_older_release(target, deployed) is older
