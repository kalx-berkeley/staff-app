"""Tests for the phase 3 migration that fills persona and show IDs from DJ names."""

import json
import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from app.config import settings

BACKEND = Path(__file__).resolve().parents[2]
BEFORE = "d6f2b8e4a0c1"
MIGRATION = "e7a3c9f5b1d2"
NOW = "2026-11-01 12:00:00"


@pytest.fixture
def database(tmp_path, monkeypatch):
    """A database migrated to just before the phase 3 migration."""
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
        "INSERT INTO staff (id, email, name, phone, dj_personas, spinitron_ids,"
        " created_at, updated_at) VALUES (1, 'one@example.com', 'One', '', ?, ?, ?, ?)",
        (json.dumps([{"id": 11, "name": "DJ One"}]), json.dumps([11]), NOW, NOW),
    )
    # A former DJ known only from the nightly copy of Spinitron's directory
    run(
        "INSERT INTO spinitron_personas (id, name, updated_at) VALUES (12, 'DJ Gone', ?)",
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
    run("INSERT INTO dj_name_mappings (name_key, created_at) VALUES ('unknown', ?)", (NOW,))
    run(
        "INSERT INTO dj_name_mappings (name_key, persona_id, created_at)"
        " VALUES ('dj fooo', 11, ?)",
        (NOW,),
    )
    passes = [
        # id, given away by, pre-assigned to, pre-assigned show
        (1, "dj one ", None, None),
        (2, "Take Five", None, None),
        (3, "Unknown", None, None),
        (4, "DJ Fooo", None, None),
        (5, None, "DJ Gone", None),
        (6, None, "Take Five", 1),
    ]
    for pass_id, given, preassigned, preassigned_show in passes:
        run(
            "INSERT INTO passes (id, show_id, pass_type, status, given_away_by_dj,"
            " preassigned_dj, preassigned_specialty_show_id, created_at, updated_at)"
            " VALUES (?, 1, 'pair', 'given_away', ?, ?, ?, ?, ?)",
            (pass_id, given, preassigned, preassigned_show, NOW, NOW),
        )
    run(
        "INSERT INTO on_air_winners (pass_id, venue_id, show_id, recipient_name,"
        " recipient_phone, given_away_by_dj, created_at)"
        " VALUES (2, 1, 1, 'Winner', '555', 'Morning Report', ?)",
        (NOW,),
    )
    run(
        "INSERT INTO show_attempts (show_id, dj_name, attempted_at) VALUES (1, 'DJ"
        " Gone', ?)",
        (NOW,),
    )
    run("INSERT INTO specialty_show_djs (specialty_show_id, dj_name) VALUES (1, 'DJ Gone')")
    run(
        "INSERT INTO analytics_event (occurred_at, event_type, area, dj_name)"
        " VALUES (?, 'giveaway', 'pass-giveaway', 'take five')",
        (NOW,),
    )
    run(
        "INSERT INTO analytics_daily_count (day, event_type, area, dj_name, count)"
        " VALUES ('2025-01-01', 'giveaway', 'pass-giveaway', 'dj one', 3)"
    )
    conn.commit()


def rows(conn, sql: str) -> list[tuple]:
    return conn.execute(sql).fetchall()


def test_fills_every_record(database):
    conn, config = database
    command.upgrade(config, MIGRATION)

    assert rows(
        conn,
        "SELECT id, given_away_persona_id, given_away_specialty_show_id,"
        " preassigned_persona_id, preassigned_specialty_show_id FROM passes ORDER BY id",
    ) == [
        (1, 11, None, None, None),
        (2, None, 1, None, None),
        # Mapped to no one: unattributed
        (3, None, None, None, None),
        # Mapped by hand
        (4, 11, None, None, None),
        # A former DJ, from the nightly persona directory
        (5, None, None, 12, None),
        # Already pre-assigned to a show: left alone
        (6, None, None, None, 1),
    ]
    assert rows(
        conn,
        "SELECT given_away_persona_id, given_away_specialty_show_id FROM on_air_winners",
    ) == [(None, 2)]
    assert rows(conn, "SELECT persona_id, specialty_show_id FROM show_attempts") == [
        (12, None)
    ]
    assert rows(conn, "SELECT persona_id FROM specialty_show_djs") == [(12,)]
    assert rows(conn, "SELECT persona_id, specialty_show_id FROM analytics_event") == [
        (None, 1)
    ]
    assert rows(
        conn, "SELECT persona_id, specialty_show_id FROM analytics_daily_count"
    ) == [(11, None)]

    command.downgrade(config, BEFORE)
    columns = [r[1] for r in rows(conn, "PRAGMA table_info(passes)")]
    assert "given_away_persona_id" not in columns


def test_refuses_while_any_name_is_unmatched(database):
    conn, config = database
    conn.execute(
        "INSERT INTO show_attempts (show_id, dj_name, attempted_at) VALUES (1, 'DJ"
        " Typo', ?)",
        (NOW,),
    )
    # A name a show and a persona share is ambiguous
    conn.execute(
        "INSERT INTO spinitron_personas (id, name, updated_at) VALUES (13, 'Take Five', ?)",
        (NOW,),
    )
    conn.commit()

    with pytest.raises(RuntimeError) as error:
        command.upgrade(config, MIGRATION)

    message = str(error.value)
    assert "show_attempts.dj_name 'DJ Typo': no persona or show has this name" in message
    assert "passes.given_away_by_dj 'Take Five': a show and a persona share" in message
    assert "spinitron_identity_report.py" in message
    # Nothing changed
    columns = [r[1] for r in rows(conn, "PRAGMA table_info(passes)")]
    assert "given_away_persona_id" not in columns
