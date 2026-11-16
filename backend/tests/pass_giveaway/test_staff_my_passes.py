"""Tests for the signed-in /staff My Passes giveaway history (decision 27)."""

from datetime import date, datetime, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.pass_model import Pass
from app.models.show import Show
from app.models.specialty_show import SpecialtyShow
from app.models.specialty_show_dj import SpecialtyShowDJ
from app.models.staff import Staff
from app.models.staff_status import StaffStatus
from app.models.talk_show_staff import TalkShowStaff
from app.models.venue import Venue
from tests.personas import dj_fields

URL = "/api/passes/staff/my-giveaways"


def _staff(db: Session, email: str, statuses=("Active",), **fields) -> Staff:
    staff = Staff(email=email, name=email.split("@")[0].title(), phone="555", **fields)
    db.add(staff)
    db.flush()
    for s in statuses:
        db.add(StaffStatus(staff_id=staff.id, status=s))
    db.commit()
    return staff


@pytest.fixture
def show(db: Session) -> Show:
    venue = Venue(name="Venue", address="1 Main St")
    db.add(venue)
    db.flush()
    show = Show(
        event_name="Test Band",
        genre=["Rock"],
        venue_id=venue.id,
        show_date=date(2099, 12, 31),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible="yes",
        num_pass_pairs=6,
        status="published",
    )
    db.add(show)
    db.commit()
    return show


def _given(db: Session, show: Show, persona_id=None, show_id=None) -> Pass:
    p = Pass(
        show_id=show.id,
        pass_type="pair",
        status="given_away",
        given_away_at=datetime(2099, 1, 1),
        given_away_persona_id=persona_id,
        given_away_specialty_show_id=show_id,
    )
    db.add(p)
    db.commit()
    return p


def _reserved(db: Session, show: Show, persona_id=None, show_id=None) -> Pass:
    p = Pass(
        show_id=show.id,
        pass_type="pair",
        status="available",
        preassigned_dj="someone",
        preassigned_persona_id=persona_id,
        preassigned_specialty_show_id=show_id,
        preassigned_date=date(2099, 12, 30),
    )
    db.add(p)
    db.commit()
    return p


def _ids(client: TestClient, staff: Staff) -> list[int]:
    response = client.get(URL, headers={"X-Forwarded-User": staff.email})
    assert response.status_code == 200, response.text
    return sorted(p["id"] for p in response.json())


def test_covers_every_persona_and_show_the_dj_belongs_to(
    client: TestClient, db: Session, show
):
    dj = _staff(
        db, "dj@test.com", ("Active", "Sublist DJ"), **dj_fields("A", "B", ids=[1, 2])
    )
    music = SpecialtyShow(name="Take Five")
    other = SpecialtyShow(name="Someone Else's Show")
    db.add_all([music, other])
    db.flush()
    db.add(SpecialtyShowDJ(specialty_show_id=music.id, dj_name="B", persona_id=2))
    db.commit()

    mine = [
        _given(db, show, persona_id=1),
        _given(db, show, persona_id=2),
        _given(db, show, show_id=music.id),
        _reserved(db, show, persona_id=1),
        _reserved(db, show, show_id=music.id),
    ]
    _given(db, show, persona_id=3)
    _given(db, show, show_id=other.id)
    _given(db, show)

    assert _ids(client, dj) == sorted(p.id for p in mine)


def test_a_talk_show_member_who_is_not_a_sublist_dj_sees_the_shows_passes(
    client: TestClient, db: Session, show
):
    host = _staff(db, "host@test.com")
    talk = SpecialtyShow(name="Morning Report", category="talk")
    db.add(talk)
    db.flush()
    db.add(TalkShowStaff(specialty_show_id=talk.id, staff_id=host.id))
    db.commit()
    given = _given(db, show, show_id=talk.id)

    assert _ids(client, host) == [given.id]


def test_reserved_passes_count_only_on_published_shows(
    client: TestClient, db: Session, show
):
    dj = _staff(db, "dj@test.com", ("Active", "Sublist DJ"), **dj_fields("A", ids=[1]))
    reserved = _reserved(db, show, persona_id=1)
    assert _ids(client, dj) == [reserved.id]

    show.status = "closed"
    db.commit()
    assert _ids(client, dj) == []


def test_someone_with_no_personas_or_shows_has_none(client: TestClient, db: Session, show):
    _given(db, show)
    assert _ids(client, _staff(db, "plain@test.com")) == []


def test_needs_current_staff(client: TestClient, db: Session):
    gone = _staff(db, "gone@test.com", ("Inactive",))
    response = client.get(URL, headers={"X-Forwarded-User": gone.email})
    assert response.status_code in (401, 403)
