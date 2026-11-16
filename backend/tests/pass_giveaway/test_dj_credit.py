"""Tests for who the DJ pages credit: the early switch, unassigning and names."""

from datetime import date, datetime, time, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.credit import credit_label
from app.models.pass_model import Pass
from app.models.show import Show
from app.models.specialty_show import SpecialtyShow
from app.models.spinitron_persona import SpinitronPersona
from app.models.spinitron_playlist import SpinitronPlaylist
from app.models.venue import Venue
from app.pass_giveaway.services.on_air_identity import SWITCH_HEADER

DJ_STUDIO = {"X-Forwarded-For": "192.168.1.100"}


@pytest.fixture
def show(db: Session) -> Show:
    venue = Venue(name="Venue", address="1 Main St")
    db.add(venue)
    db.flush()
    show = Show(
        event_name="Show",
        genre=["Rock"],
        venue_id=venue.id,
        show_date=date(2099, 12, 31),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible="yes",
        num_pass_pairs=3,
        status="published",
    )
    db.add(show)
    db.flush()
    for _ in range(3):
        db.add(Pass(show_id=show.id, pass_type="pair", status="available"))
    db.commit()
    return show


def _pairs(db: Session, show: Show) -> list[Pass]:
    return db.query(Pass).filter(Pass.show_id == show.id).order_by(Pass.id).all()


def _preassign(db: Session, pass_item: Pass, persona_id=None, show_id=None) -> None:
    pass_item.preassigned_dj = "someone"
    pass_item.preassigned_persona_id = persona_id
    pass_item.preassigned_specialty_show_id = show_id
    pass_item.preassigned_date = date(2099, 12, 30)
    db.commit()


class TestEarlySwitch:
    @pytest.fixture
    def changeover(self, db: Session):
        """DJ One's slot ends in 5 minutes; DJ Two's starts then."""
        now = datetime.now(timezone.utc)
        db.add_all([
            SpinitronPersona(id=1, name="DJ One"),
            SpinitronPersona(id=2, name="DJ Two"),
            SpinitronPlaylist(
                id=10,
                start=now - timedelta(minutes=55),
                end=now + timedelta(minutes=5),
                persona_id=1,
            ),
            SpinitronPlaylist(
                id=11,
                start=now + timedelta(minutes=5),
                end=now + timedelta(minutes=65),
                persona_id=2,
            ),
        ])
        db.commit()
        return (now + timedelta(minutes=5)).isoformat()

    def test_the_header_moves_the_credit_to_the_next_slot(
        self, client: TestClient, db: Session, show, changeover
    ):
        mine, next_djs = _pairs(db, show)[:2]
        _preassign(db, mine, persona_id=1)
        _preassign(db, next_djs, persona_id=2)

        def history(headers):
            response = client.get("/api/passes/my-giveaways", headers=headers)
            return [p["id"] for p in response.json()]

        assert history(DJ_STUDIO) == [mine.id]
        assert history({**DJ_STUDIO, SWITCH_HEADER: changeover}) == [next_djs.id]

    def test_a_switch_to_anything_but_the_next_slot_is_ignored(
        self, client: TestClient, db: Session, show, changeover
    ):
        mine = _pairs(db, show)[0]
        _preassign(db, mine, persona_id=1)
        later = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        for value in (later, "not a time"):
            response = client.get(
                "/api/passes/my-giveaways", headers={**DJ_STUDIO, SWITCH_HEADER: value}
            )
            assert [p["id"] for p in response.json()] == [mine.id]


class TestUnassignFromTheStudio:
    def _unassign(self, client: TestClient, pass_item: Pass):
        return client.delete(f"/api/passes/{pass_item.id}/preassign", headers=DJ_STUDIO)

    def test_only_who_is_on_air_unassigns_their_passes(
        self, client: TestClient, db: Session, show, on_air
    ):
        mine, theirs = _pairs(db, show)[:2]
        _preassign(db, mine, persona_id=1)
        _preassign(db, theirs, persona_id=2)
        on_air(persona_id=1, name="DJ One")

        assert self._unassign(client, theirs).status_code == 403
        assert self._unassign(client, mine).status_code == 200
        on_air(None)
        assert self._unassign(client, theirs).status_code == 403

    def test_a_music_show_slot_unassigns_the_shows_and_its_djs_passes(
        self, client: TestClient, db: Session, show, on_air
    ):
        take_five = SpecialtyShow(name="Take Five")
        db.add(take_five)
        db.commit()
        for_show, for_dj, other = _pairs(db, show)
        _preassign(db, for_show, show_id=take_five.id)
        _preassign(db, for_dj, persona_id=1)
        _preassign(db, other, persona_id=2)
        on_air(kind="music", name="Take Five", specialty_show_id=take_five.id, persona_id=1)

        assert self._unassign(client, for_show).status_code == 200
        assert self._unassign(client, for_dj).status_code == 200
        assert self._unassign(client, other).status_code == 403

    def test_a_talk_show_slot_unassigns_only_the_shows_passes(
        self, client: TestClient, db: Session, show, on_air
    ):
        talk = SpecialtyShow(name="Morning Report", category="talk")
        db.add(talk)
        db.commit()
        for_show, for_host = _pairs(db, show)[:2]
        _preassign(db, for_show, show_id=talk.id)
        _preassign(db, for_host, persona_id=1)
        on_air(kind="talk", name="Morning Report", specialty_show_id=talk.id, persona_id=1)

        assert self._unassign(client, for_host).status_code == 403
        assert self._unassign(client, for_show).status_code == 200


class TestCreditLabel:
    def test_names_are_current(self, db: Session):
        db.add(SpinitronPersona(id=1, name="DJ Renamed"))
        music = SpecialtyShow(name="Take Five")
        db.add(music)
        db.commit()
        assert credit_label(db, 1, None, "DJ Old") == "DJ Renamed"
        assert credit_label(db, 2, None, "DJ Old") == "DJ Old"
        assert credit_label(db, 2, None) == "Persona #2"
        assert credit_label(db, None, music.id) == "Take Five"
        assert credit_label(db, 1, music.id) == "Take Five (DJ Renamed)"
        assert credit_label(db, None, None, "Unknown") == "Unattributed"
