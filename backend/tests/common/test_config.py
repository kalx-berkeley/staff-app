"""Tests for loading settings from .env, and flagging keys that aren't settings."""

import logging
from pathlib import Path
from unittest.mock import patch

from app.config import Settings, unknown_env_file_keys
from app.main import check_env_file


def _env_file(tmp_path: Path, text: str) -> str:
    path = tmp_path / ".env"
    path.write_text(text)
    return str(path)


def test_unknown_key_doesnt_stop_settings_loading(tmp_path):
    """A leftover line, like a removed feature's flag, is ignored."""
    env_file = _env_file(tmp_path, "ENVIRONMENT=staging\nLEGACY_IMPORT_ENABLED=true\n")

    settings = Settings(_env_file=env_file)

    assert settings.environment == "staging"
    assert not hasattr(settings, "legacy_import_enabled")


def test_unknown_env_file_keys_lists_only_unknown_keys(tmp_path):
    env_file = _env_file(
        tmp_path,
        "# a comment\n"
        "environment=staging\n"
        "DATABASE_URL=sqlite:///x.db\n"
        "SITE_ADMIN_EMAILS=\n"
        "LEGACY_IMPORT_ENABLED=true\n"
        "ENVIROMENT=production\n",
    )

    assert unknown_env_file_keys(env_file) == ["ENVIROMENT", "LEGACY_IMPORT_ENABLED"]


def test_unknown_env_file_keys_without_a_file(tmp_path):
    assert unknown_env_file_keys(None) == []
    assert unknown_env_file_keys(str(tmp_path / "missing.env")) == []


def test_check_env_file_logs_each_unknown_key(tmp_path, caplog):
    env_file = _env_file(tmp_path, "ENVIRONMENT=staging\nLEGACY_IMPORT_ENABLED=true\n")

    with patch("app.main.unknown_env_file_keys", lambda: unknown_env_file_keys(env_file)):
        with caplog.at_level(logging.ERROR, logger="app.main"):
            check_env_file()

    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == [
        "Unknown setting LEGACY_IMPORT_ENABLED in .env is ignored. "
        "Remove it, or check its spelling."
    ]


def test_check_env_file_is_quiet_when_every_key_is_known(tmp_path, caplog):
    env_file = _env_file(tmp_path, "ENVIRONMENT=staging\n")

    with patch("app.main.unknown_env_file_keys", lambda: unknown_env_file_keys(env_file)):
        with caplog.at_level(logging.ERROR, logger="app.main"):
            check_env_file()

    assert not caplog.records
