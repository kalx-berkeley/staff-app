"""Tests for re-crediting giveaways in Promotions → Admin (decision 28)."""

from datetime import date, datetime, time, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.common.areas import PASS_GIVEAWAY_AREA
from app.models.audit_log import AuditLog
from app.models.on_air_winner import OnAirWinner
from app.models.pass_model import Pass
from app.models.show import Show
from app.models.specialty_show import SpecialtyShow
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus
from app.models.venue import Venue
from tests.personas import dj_fields

URL = "/api/pass-giveaway/admin"
NOW = datetime.now(timezone.utc).replace(tzinfo=None)


def _staff(db: Session, email: str, department: str | None = None, **fields) -> Staff:
    staff = Staff(email=email, name=email.split("@")[0].title(), phone="555", **fields)
    db.add(staff)
    db.flush()
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    if department:
        db.add(StaffDepartment(staff_id=staff.id, department=department))
    db.commit()
    return staff


@pytest.fixture
def promo(db: Session) -> dict:
    return {"X-Forwarded-User": _staff(db, "promo@test.com", "Promotions").email}


@pytest.fixture
def giveaways(db: Session) -> dict:
    """An unattributed giveaway, one credited to DJ One, and an old one."""
    _staff(db, "dj@test.com", **dj_fields("DJ One", ids=[11]))
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
        num_pass_pairs=3,
        status="published",
    )
    db.add(show)
    db.flush()

    def given(when: datetime, persona_id=None) -> Pass:
        p = Pass(
            show_id=show.id,
            pass_type="pair",
            status="given_away",
            given_away_at=when,
            given_away_persona_id=persona_id,
        )
        db.add(p)
        db.flush()
        db.add(
            OnAirWinner(
                pass_id=p.id,
                venue_id=venue.id,
                show_id=show.id,
                recipient_name=f"Winner {p.id}",
                recipient_phone="5105550100",
                given_away_persona_id=persona_id,
            )
        )
        return p

    found = {
        "unattributed": given(NOW - timedelta(hours=1)),
        "credited": given(NOW - timedelta(hours=2), persona_id=11),
        "old": given(NOW - timedelta(days=200)),
    }
    db.commit()
    return found


def test_lists_recent_giveaways_newest_first(client: TestClient, promo, giveaways):
    response = client.get(f"{URL}/giveaways", headers=promo)

    assert response.status_code == 200
    rows = response.json()
    assert [r["pass_id"] for r in rows] == [
        giveaways["unattributed"].id,
        giveaways["credited"].id,
    ]
    assert [r["credited_to"] for r in rows] == ["Unattributed", "DJ One"]
    assert rows[0]["recipient_name"] == f"Winner {giveaways['unattributed'].id}"


def test_lists_only_unattributed_giveaways(client: TestClient, promo, giveaways):
    response = client.get(
        f"{URL}/giveaways", params={"unattributed": True, "days": 365}, headers=promo
    )

    assert [r["pass_id"] for r in response.json()] == [
        giveaways["unattributed"].id,
        giveaways["old"].id,
    ]


def test_recredits_to_a_show_and_logs_it(client: TestClient, db: Session, promo, giveaways):
    music = SpecialtyShow(name="Take Five")
    db.add(music)
    db.commit()
    pass_item = giveaways["credited"]

    response = client.put(
        f"{URL}/giveaways/{pass_item.id}/credit",
        json={"specialty_show_id": music.id},
        headers=promo,
    )

    assert response.status_code == 200, response.text
    assert response.json()["credited_to"] == "Take Five"
    db.refresh(pass_item)
    assert (pass_item.given_away_persona_id, pass_item.given_away_specialty_show_id) == (
        None,
        music.id,
    )
    assert pass_item.on_air_winner.given_away_specialty_show_id == music.id
    entry = db.query(AuditLog).filter(AuditLog.event_type == "giveaway_recredited").one()
    assert entry.area == PASS_GIVEAWAY_AREA
    assert entry.actor_email == "promo@test.com"
    assert entry.details["before"]["dj"] == "DJ One"
    assert entry.details["after"]["specialty_show_id"] == music.id


def test_recredits_an_unattributed_giveaway_to_a_persona(
    client: TestClient, db: Session, promo, giveaways
):
    pass_item = giveaways["unattributed"]
    response = client.put(
        f"{URL}/giveaways/{pass_item.id}/credit", json={"persona_id": 11}, headers=promo
    )

    assert response.json()["credited_to"] == "DJ One"
    db.refresh(pass_item)
    assert pass_item.on_air_winner.given_away_persona_id == 11


def test_can_clear_a_credit(client: TestClient, db: Session, promo, giveaways):
    pass_item = giveaways["credited"]
    response = client.put(f"{URL}/giveaways/{pass_item.id}/credit", json={}, headers=promo)

    assert response.json()["credited_to"] == "Unattributed"


def test_refuses_a_persona_no_current_staff_member_holds(
    client: TestClient, promo, giveaways
):
    response = client.put(
        f"{URL}/giveaways/{giveaways['unattributed'].id}/credit",
        json={"persona_id": 999},
        headers=promo,
    )

    assert response.status_code == 400


def test_refuses_a_pass_that_was_not_given_away(
    client: TestClient, db: Session, promo, giveaways
):
    pass_item = giveaways["unattributed"]
    pass_item.status = "available"
    db.commit()

    response = client.put(
        f"{URL}/giveaways/{pass_item.id}/credit", json={"persona_id": 11}, headers=promo
    )

    assert response.status_code == 400


def test_is_for_promotions_and_site_admins_only(client: TestClient, db: Session, giveaways):
    staffer = {"X-Forwarded-User": _staff(db, "staffer@test.com").email}

    assert client.get(f"{URL}/giveaways", headers=staffer).status_code == 403
    assert (
        client.put(
            f"{URL}/giveaways/{giveaways['unattributed'].id}/credit",
            json={"persona_id": 11},
            headers=staffer,
        ).status_code
        == 403
    )


def test_offers_staff_personas_and_shows(client: TestClient, db: Session, promo, giveaways):
    db.add(SpecialtyShow(name="Take Five"))
    db.commit()

    response = client.get(f"{URL}/credit-identities", headers=promo)

    assert [(i["kind"], i["name"]) for i in response.json()] == [
        ("persona", "DJ One"),
        ("music", "Take Five"),
    ]
