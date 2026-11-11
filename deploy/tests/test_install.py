"""Tests for install.py: Node updates, settings, and what happens on failure."""

import datetime
import hashlib
import io
import json
import sqlite3
import tarfile
import urllib.error
from pathlib import Path

import pytest

import install
from conftest import write_env
from deploy_common import get_environment, read_state


def fake_node(home: Path, version: str) -> Path:
    """Make an installed Node directory."""
    directory = home / "opt" / f"node-{version}-linux-x64"
    (directory / "bin").mkdir(parents=True)
    (directory / "bin" / "node").write_text("")
    return directory


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class NodeIndex:
    """A fake nodejs.org release list, and the requests made for it."""

    def __init__(self) -> None:
        self.releases = [
            {"version": "v28.0.0", "files": ["linux-x64"]},
            {"version": "v26.2.1", "files": ["linux-x64"]},
            {"version": "v26.2.0", "files": ["linux-x64"]},
        ]
        self.offline = False
        self.requests: list[str] = []


@pytest.fixture
def node_index(monkeypatch: pytest.MonkeyPatch) -> NodeIndex:
    """Serve a Node release list, and record installs instead of downloading."""
    index = NodeIndex()

    def urlopen(request, timeout=None):
        index.requests.append(request.full_url)
        if index.offline:
            raise urllib.error.URLError("offline")
        return FakeResponse(json.dumps(index.releases).encode())

    monkeypatch.setattr(install.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(install.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(
        install, "install_node", lambda version: fake_node(Path.home(), version)
    )
    return index


def test_ensure_node_installs_the_newest_of_the_major(home, node_index):
    assert install.ensure_node(26) == home / "opt" / "node-v26.2.1-linux-x64" / "bin"


def test_ensure_node_checks_at_most_once_a_day(home, node_index):
    install.ensure_node(26)
    install.ensure_node(26)
    assert len(node_index.requests) == 1


def test_ensure_node_keeps_two_versions(home, node_index):
    for version in ("v26.0.0", "v26.1.0", "v26.2.0"):
        fake_node(home, version)
    install.ensure_node(26)
    assert sorted(path.name for path in (home / "opt").glob("node-*")) == [
        "node-v26.2.0-linux-x64",
        "node-v26.2.1-linux-x64",
    ]


def test_ensure_node_uses_what_is_installed_when_offline(home, node_index):
    fake_node(home, "v26.1.0")
    node_index.offline = True
    assert install.ensure_node(26) == home / "opt" / "node-v26.1.0-linux-x64" / "bin"


def test_ensure_node_fails_offline_with_nothing_installed(home, node_index):
    node_index.offline = True
    with pytest.raises(RuntimeError, match="No Node 26 is installed"):
        install.ensure_node(26)


def test_install_node_rejects_a_bad_checksum(home, monkeypatch):
    (home / "opt").mkdir()
    name = "node-v26.2.1-linux-x64"
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w:gz") as archive:
        info = tarfile.TarInfo(f"{name}/bin/node")
        archive.addfile(info, io.BytesIO(b""))
    good = hashlib.sha256(payload.getvalue()).hexdigest()

    def download(url: str, destination: Path) -> None:
        if url.endswith("SHASUMS256.txt"):
            destination.write_text(f"{checksum}  {name}.tar.gz\n")
        else:
            destination.write_bytes(payload.getvalue())

    monkeypatch.setattr(install, "download", download)
    checksum = "0" * 64
    with pytest.raises(ValueError, match="SHA-256"):
        install.install_node("v26.2.1")
    assert not (home / "opt" / name).exists()

    checksum = good
    assert install.install_node("v26.2.1") == home / "opt" / name
    assert (home / "opt" / name / "bin" / "node").exists()


def test_set_app_version_replaces_only_that_line(home):
    path = write_env(
        home, "staging", "WEBMASTER_EMAIL=web@example.com\nAPP_VERSION=old\nX=1\n"
    )
    install.set_app_version(get_environment("staging"), "new")
    assert path.read_text() == "WEBMASTER_EMAIL=web@example.com\nAPP_VERSION=new\nX=1\n"
    assert path.stat().st_mode & 0o777 == 0o600


def test_set_app_version_adds_a_missing_line(home):
    path = write_env(home, "staging", "X=1\n")
    install.set_app_version(get_environment("staging"), "new")
    assert path.read_text() == "X=1\nAPP_VERSION=new\n"


def test_backup_database_copies_the_data(home):
    data = home / "staff-app-production" / "backend" / "data"
    data.mkdir(parents=True)
    with sqlite3.connect(data / "staff-app.db") as connection:
        connection.execute("create table shows (name text)")
        connection.execute("insert into shows values ('Rhye')")
    backup = install.backup_database(get_environment("production"))
    with sqlite3.connect(backup) as connection:
        assert connection.execute("select name from shows").fetchall() == [("Rhye",)]


def test_production_installs_its_own_units_and_the_shared_templates():
    assert install.units_for(get_environment("production")) == [
        "staff-app-backend-production.service",
        "staff-app-deploy-production.timer",
        "staff-app-deploy@.service",
        "staff-app-deploy-failed@.service",
    ]
    assert install.units_for(get_environment("staging")) == [
        "staff-app-backend-staging.service",
        "staff-app-deploy-staging.timer",
    ]


def test_every_installed_unit_exists_in_the_repo():
    systemd = Path(__file__).resolve().parents[2] / "systemd"
    for environment in ("staging", "production"):
        for name in install.units_for(get_environment(environment)):
            assert (systemd / name).exists(), name


@pytest.fixture
def steps(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace each install step with a recorder."""
    calls: list[str] = []
    monkeypatch.setattr(install, "build_frontend", lambda *a: calls.append("build"))
    monkeypatch.setattr(install, "backup_database", lambda *a: calls.append("backup"))
    monkeypatch.setattr(
        install,
        "take_snapshot",
        lambda *a: calls.append("snapshot") or install.Snapshot(Path()),
    )
    monkeypatch.setattr(install, "install", lambda *a: calls.append("install"))
    monkeypatch.setattr(
        install, "rollback", lambda *a: calls.append("rollback") or "Rolled back fine."
    )
    monkeypatch.setattr(install, "finish", lambda *a: calls.append("finish"))
    monkeypatch.setattr(install.os, "chmod", lambda *a: None)
    return calls


def run_install(environment: str) -> int:
    return install.main([environment, "--version", "v2", "--previous", "v1"])


def test_production_install_runs_every_step(steps):
    assert run_install("production") == 0
    assert steps == ["build", "backup", "snapshot", "install", "finish"]


def test_staging_takes_no_snapshot(steps):
    assert run_install("staging") == 0
    assert steps == ["build", "backup", "install", "finish"]


def test_a_failed_production_install_rolls_back(steps, monkeypatch):
    def broken(*args):
        steps.append("install")
        raise RuntimeError("alembic exploded")

    monkeypatch.setattr(install, "install", broken)
    assert run_install("production") == 1
    assert steps == ["build", "backup", "snapshot", "install", "rollback"]
    reason = read_state(get_environment("production"), "last-failure")
    assert "alembic exploded" in reason and "Rolled back fine." in reason


def test_a_failed_staging_install_is_left_as_it_is(steps, monkeypatch):
    def broken(*args):
        steps.append("install")
        raise RuntimeError("alembic exploded")

    monkeypatch.setattr(install, "install", broken)
    assert run_install("staging") == 1
    assert "rollback" not in steps
    assert "left as it is" in read_state(get_environment("staging"), "last-failure")


def test_a_failed_build_changes_nothing(steps, monkeypatch):
    def broken(*args):
        raise RuntimeError("npm ci failed")

    monkeypatch.setattr(install, "build_frontend", broken)
    assert run_install("production") == 1
    assert steps == []
    reason = read_state(get_environment("production"), "last-failure")
    assert "nothing was changed and v1 is still live" in reason
    assert "building the frontend" in reason


def test_finish_records_the_version_and_updates_the_stable_scripts(home, monkeypatch):
    emails = []
    monkeypatch.setattr(install, "send_email", lambda *args: emails.append(args[1]))
    source = Path(__file__).resolve().parents[2]
    install.finish(source, get_environment("production"), "v2")
    assert (home / "staff-app-production" / "DEPLOYED_VERSION").read_text() == "v2\n"
    for name in install.STABLE_FILES:
        assert (home / "staff-app-deploy" / "production" / name).exists()
    assert emails == ["[KALX Staff App] v2 deployed to production"]


def test_today_is_used_for_the_daily_node_check(home, node_index):
    install.ensure_node(26)
    assert (home / "opt" / ".checked-node-26").read_text().strip() == (
        datetime.date.today().isoformat()
    )


def test_a_snapshot_of_a_new_environment_is_empty(home):
    snapshot = install.take_snapshot(get_environment("production"))
    assert list((snapshot.directory / "backend").iterdir()) == []
    assert list((snapshot.directory / "dist").iterdir()) == []
    assert snapshot.units == []


def test_rsync_removes_folders_left_holding_only_caches(tmp_path):
    source = tmp_path / "source"
    (source / "app" / "common").mkdir(parents=True)
    (source / "app" / "common" / "users.py").write_text("")
    live = tmp_path / "live"
    for path in (
        "app/routers/__pycache__/old.cpython-312.pyc",
        "app/common/__pycache__/users.cpython-312.pyc",
        "venv/bin/python",
        "data/staff-app.db",
        ".env",
    ):
        (live / path).parent.mkdir(parents=True, exist_ok=True)
        (live / path).write_text("keep?")
    install.rsync(source, live, install.BACKEND_RSYNC_FILTERS)
    assert not (live / "app" / "routers").exists()
    for kept in ("venv/bin/python", "data/staff-app.db", ".env", "app/common/users.py"):
        assert (live / kept).exists(), kept
