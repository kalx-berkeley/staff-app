"""Tests for the phase 4 migration that drops the DJ name text columns."""

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from app.config import settings

BACKEND = Path(__file__).resolve().parents[2]
BEFORE = "e7a3c9f5b1d2"
MIGRATION = "a1d7e3f9c5b8"
NOW = "2026-11-01 12:00:00"


@pytest.fixture
def database(tmp_path, monkeypatch):
    """A database migrated to just before the phase 4 migration."""
    path = tmp_path / "staff-app.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{path}")
    # No config file, so Alembic leaves the app's logging alone
    config = Config()
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    command.upgrade(config, BEFORE)
    conn = sqlite3.connect(path)
    seed(conn)
    yield conn, config
    conn.close()


def seed(conn: sqlite3.Connection) -> None:
    run = conn.execute
    run(
        "INSERT INTO spinitron_personas (id, name, updated_at) VALUES (11, 'DJ One', ?)",
        (NOW,),
    )
    for show_id, name, category in (
        (1, "Take Five", "music"),
        (2, "Morning Report", "talk"),
    ):
        run(
            "INSERT INTO specialty_shows (id, name, category, deleted,"
            " created_at, updated_at) VALUES (?, ?, ?, 0, ?, ?)",
            (show_id, name, category, NOW, NOW),
        )
    passes = [
        # id, given away by, persona, show, pre-assigned to, persona, show
        (1, "DJ Onee", 11, None, None, None, None),
        (2, "Take Five (DJ One)", 11, 1, None, None, None),
        # Unattributed since phase 3: no name
        (3, None, None, None, None, None, None),
        (4, None, None, None, "Morning Report", None, 2),
    ]
    for row in passes:
        run(
            "INSERT INTO passes (id, show_id, pass_type, status, given_away_by_dj,"
            " given_away_persona_id, given_away_specialty_show_id, preassigned_dj,"
            " preassigned_persona_id, preassigned_specialty_show_id, created_at,"
            " updated_at) VALUES (?, 1, 'pair', 'given_away', ?, ?, ?, ?, ?, ?, ?, ?)",
            (*row, NOW, NOW),
        )
    run(
        "INSERT INTO on_air_winners (pass_id, venue_id, show_id, recipient_name,"
        " recipient_phone, given_away_by_dj, given_away_persona_id, created_at)"
        " VALUES (1, 1, 1, 'Winner', '555', 'DJ Onee', 11, ?)",
        (NOW,),
    )
    run(
        "INSERT INTO show_attempts (show_id, dj_name, persona_id, attempted_at)"
        " VALUES (1, 'DJ One', 11, ?)",
        (NOW,),
    )
    run(
        "INSERT INTO lottery_entries (show_id, entry_type, dj_name, specialty_show_id,"
        " status, entered_at, created_at, updated_at)"
        " VALUES (1, 'dj', 'Morning Report', 2, 'pending', ?, ?, ?)",
        (NOW, NOW, NOW),
    )
    run(
        "INSERT INTO specialty_show_djs (specialty_show_id, dj_name, persona_id)"
        " VALUES (1, 'DJ One', 11)"
    )
    # Two counts that differ only by the typed name become one
    for dj_name, count in (("dj one", 3), ("dj onee", 2)):
        run(
            "INSERT INTO analytics_daily_count (day, event_type, area, dj_name,"
            " persona_id, count) VALUES ('2025-01-01', 'giveaway', 'pass-giveaway',"
            " ?, 11, ?)",
            (dj_name, count),
        )
    conn.commit()


def rows(conn, sql: str) -> list[tuple]:
    return conn.execute(sql).fetchall()


def columns(conn, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def test_drops_the_text_columns(database):
    conn, config = database
    command.upgrade(config, MIGRATION)

    assert "preassigned_dj" not in columns(conn, "passes")
    assert "given_away_by_dj" not in columns(conn, "passes")
    assert "given_away_by_dj" not in columns(conn, "on_air_winners")
    for table in (
        "show_attempts",
        "lottery_entries",
        "specialty_show_djs",
        "analytics_event",
        "analytics_daily_count",
    ):
        assert "dj_name" not in columns(conn, table), table
    assert not rows(conn, "SELECT name FROM sqlite_master WHERE name = 'dj_name_mappings'")
    assert rows(conn, "SELECT persona_id, count FROM analytics_daily_count") == [(11, 5)]

    command.downgrade(config, BEFORE)
    assert rows(
        conn, "SELECT id, given_away_by_dj, preassigned_dj FROM passes ORDER BY id"
    ) == [
        # Current names, not the typed ones
        (1, "DJ One", None),
        (2, "Take Five (DJ One)", None),
        (3, None, None),
        (4, None, "Morning Report"),
    ]
    assert rows(conn, "SELECT given_away_by_dj FROM on_air_winners") == [("DJ One",)]
    assert rows(conn, "SELECT dj_name FROM lottery_entries") == [("Morning Report",)]
    assert rows(conn, "SELECT dj_name FROM specialty_show_djs") == [("DJ One",)]
    assert rows(conn, "SELECT dj_name, count FROM analytics_daily_count") == [("dj one", 5)]


def test_refuses_while_a_name_has_no_persona_or_show(database):
    conn, config = database
    conn.execute(
        "INSERT INTO show_attempts (show_id, dj_name, attempted_at) VALUES (1, 'DJ"
        " Who', ?)",
        (NOW,),
    )
    conn.commit()

    with pytest.raises(RuntimeError, match=r"show_attempts\.dj_name 'DJ Who': 1 record"):
        command.upgrade(config, MIGRATION)
    assert "dj_name" in columns(conn, "show_attempts")


def test_allows_a_name_mapped_to_no_one(database):
    conn, config = database
    conn.execute(
        "INSERT INTO show_attempts (show_id, dj_name, attempted_at) VALUES (1,"
        " 'Unknown', ?)",
        (NOW,),
    )
    conn.execute(
        "INSERT INTO dj_name_mappings (name_key, created_at) VALUES ('unknown', ?)", (NOW,)
    )
    conn.commit()

    command.upgrade(config, MIGRATION)
    assert "dj_name" not in columns(conn, "show_attempts")
