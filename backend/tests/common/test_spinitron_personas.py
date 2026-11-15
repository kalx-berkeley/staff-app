"""Tests for the Spinitron persona table: its sync, names and inactive personas."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app import config
from app.common.services.spinitron_personas import (
    offered_personas,
    persona_names,
    sync_personas,
)
from app.models.job_log import JobLog
from app.models.spinitron_persona import SpinitronPersona
from app.models.staff import Staff
from tests.personas import dj_fields

SERVICE = "app.common.services.spinitron_personas.SpinitronService"
NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


def _staff(db: Session, email: str, personas: list[tuple[int, str]]) -> Staff:
    staff = Staff(
        email=email,
        name=email,
        phone="",
        **dj_fields(*[n for _, n in personas], ids=[i for i, _ in personas]),
    )
    db.add(staff)
    db.commit()
    return staff


@pytest.fixture
def spinitron(monkeypatch):
    """Spinitron with three personas; personas 1 and 2 have played."""
    monkeypatch.setattr(config.settings, "spinitron_api_key", "test-key")
    looked_up: list[int] = []

    async def fake_fetch_all_personas():
        return {1: "DJ One", 2: "DJ Two", 3: "Not Staff"}

    async def fake_fetch_last_playlist_start(persona_id):
        looked_up.append(persona_id)
        if persona_id == 4:
            raise RuntimeError("Spinitron API error 500")
        return {1: NOW, 2: NOW - timedelta(days=400)}.get(persona_id)

    monkeypatch.setattr(f"{SERVICE}.fetch_all_personas", fake_fetch_all_personas)
    monkeypatch.setattr(
        f"{SERVICE}.fetch_last_playlist_start", fake_fetch_last_playlist_start
    )
    return looked_up


async def test_sync_stores_every_name_and_staff_personas_last_playlists(
    db: Session, spinitron
):
    _staff(db, "a@test", [(1, "DJ One (old name)"), (2, "DJ Two")])
    db.add(SpinitronPersona(id=9, name="Gone From Spinitron"))
    db.commit()

    result = await sync_personas(db, trigger="manual")

    assert result == {"personas": 3, "looked_up": 2, "errors": 0}
    assert sorted(spinitron) == [1, 2]
    rows = {p.id: p for p in db.query(SpinitronPersona)}
    assert {pid: p.name for pid, p in rows.items()} == {
        1: "DJ One",
        2: "DJ Two",
        3: "Not Staff",
        9: "Gone From Spinitron",
    }
    assert rows[1].last_playlist_at.replace(tzinfo=timezone.utc) == NOW
    assert rows[3].last_playlist_at is None
    assert db.query(JobLog).filter_by(job_id="spinitron_persona_sync").count() == 1


async def test_a_failed_lookup_keeps_the_previous_date(db: Session, spinitron):
    _staff(db, "a@test", [(4, "DJ Four")])
    before = NOW - timedelta(days=10)
    db.add(SpinitronPersona(id=4, name="DJ Four", last_playlist_at=before))
    db.commit()

    result = await sync_personas(db)

    assert result["errors"] == 1
    row = db.get(SpinitronPersona, 4)
    assert row.last_playlist_at.replace(tzinfo=timezone.utc) == before


async def test_sync_does_nothing_without_an_api_key(db: Session, monkeypatch):
    monkeypatch.setattr(config.settings, "spinitron_api_key", "")

    assert await sync_personas(db) is None


def test_persona_names_fall_back_to_staff_records(db: Session):
    _staff(db, "a@test", [(1, "Staff Name"), (2, "Only On Staff")])
    db.add(SpinitronPersona(id=1, name="Spinitron Name"))
    db.commit()

    assert persona_names(db, [1, 2, 3]) == {1: "Spinitron Name", 2: "Only On Staff"}


def _played(db: Session, played: dict[int, datetime | None]) -> list[dict]:
    for pid, at in played.items():
        db.add(SpinitronPersona(id=pid, name=f"P{pid}", last_playlist_at=at))
    db.commit()
    return [{"id": pid, "name": f"P{pid}"} for pid in played]


def _ids(personas):
    return [p["id"] for p in personas]


def test_inactive_personas_are_hidden_when_another_is_active(db: Session):
    personas = _played(
        db, {1: NOW - timedelta(days=30), 2: NOW - timedelta(days=200), 3: None}
    )

    assert _ids(offered_personas(db, personas, now=NOW)) == [1]


def test_assigned_personas_are_always_offered(db: Session):
    personas = _played(db, {1: NOW, 2: None})

    assert _ids(offered_personas(db, personas, keep_ids=[2], now=NOW)) == [1, 2]


def test_every_persona_is_offered_when_none_is_active(db: Session):
    personas = _played(db, {1: NOW - timedelta(days=300), 2: None})

    assert _ids(offered_personas(db, personas, now=NOW)) == [1, 2]


def test_a_single_persona_is_always_offered(db: Session):
    personas = _played(db, {1: None})

    assert _ids(offered_personas(db, personas, now=NOW)) == [1]


def test_offered_personas_use_current_names(db: Session):
    _played(db, {1: NOW})

    assert offered_personas(db, [{"id": 1, "name": "Old"}], now=NOW) == [
        {"id": 1, "name": "P1"}
    ]
