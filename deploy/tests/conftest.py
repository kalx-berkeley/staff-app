"""Shared fixtures for the deploy script tests."""

import sys
from pathlib import Path

import pytest

# The scripts import deploy_common as a sibling, as they do on the server
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Give every test its own empty home directory.

    :param tmp_path: pytest's temporary directory
    :type tmp_path: Path
    :param monkeypatch: pytest's monkeypatch fixture
    :type monkeypatch: pytest.MonkeyPatch
    :returns: The home directory
    :rtype: Path
    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    return home


def write_env(home: Path, environment: str, text: str) -> Path:
    """
    Write an environment's backend ``.env``.

    :param home: The home directory
    :type home: Path
    :param environment: ``staging`` or ``production``
    :type environment: str
    :param text: The file's contents
    :type text: str
    :returns: The file
    :rtype: Path
    """
    path = home / f"staff-app-{environment}" / "backend" / ".env"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path
