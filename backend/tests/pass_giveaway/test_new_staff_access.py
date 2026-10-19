"""Tests for what "🆕" staff (new students, not yet Active) can do in the pass giveaway."""

from datetime import date, datetime, time, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.pass_model import Pass
from app.models.show import Show
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus
from app.models.venue import Venue

NOT_YET_ACTIVE = "Staff passes open to you once your status is Active"


def _make_staff(db: Session, email: str, status: str, department: str | None = None):
    staff = Staff(email=email, name=email.split("@")[0], phone="555-0000")
    db.add(staff)
    db.flush()
    db.add(StaffStatus(staff_id=staff.id, status=status))
    if department:
        db.add(StaffDepartment(staff_id=staff.id, department=department))
    db.commit()
    db.refresh(staff)
    return staff


@pytest.fixture
def trainee(db: Session) -> Staff:
    return _make_staff(db, "trainee@new.test", "🆕")


@pytest.fixture
def new_promo(db: Session) -> Staff:
    return _make_staff(db, "newpromo@new.test", "🆕", "Promotions")


@pytest.fixture
def show(db: Session) -> Show:
    venue = Venue(name="New Venue", address="1 Trainee St")
    db.add(venue)
    db.commit()
    show = Show(
        event_name="New Show",
        venue_id=venue.id,
        show_date=date.today() + timedelta(days=30),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible=True,
        num_pass_pairs=2,
        status="published",
        published_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db.add(show)
    db.commit()
    for _ in range(2):
        db.add(Pass(show_id=show.id, pass_type="staff", status="available"))
    db.commit()
    db.refresh(show)
    return show


def _h(staff: Staff) -> dict:
    return {"X-Forwarded-User": staff.email}


def _staff_pass(db: Session, show: Show) -> Pass:
    return db.query(Pass).filter(Pass.show_id == show.id, Pass.pass_type == "staff").first()


@pytest.mark.parametrize("who", ["trainee", "new_promo"])
def test_new_staff_cannot_claim_enter_lottery_or_join_alternates(
    client, db, show, who, request
):
    staff = request.getfixturevalue(who)
    pass_item = _staff_pass(db, show)

    claim = client.post(
        f"/api/passes/{pass_item.id}/claim",
        json={"has_guest": True, "guest_name": "Guest"},
        headers=_h(staff),
    )
    lottery = client.post(f"/api/shows/{show.id}/lottery/enter/staff", headers=_h(staff))
    alternates = client.post(f"/api/shows/{show.id}/alternates", headers=_h(staff))

    for response in (claim, lottery, alternates):
        assert response.status_code == 403
        assert response.json()["detail"] == NOT_YET_ACTIVE
    db.expire_all()
    assert db.query(Pass).filter(Pass.status == "claimed").count() == 0


def test_active_staff_can_still_claim(client, db, show):
    staff = _make_staff(db, "active@new.test", "Active")
    pass_item = _staff_pass(db, show)

    response = client.post(f"/api/passes/{pass_item.id}/claim", headers=_h(staff))

    assert response.status_code == 200
    assert response.json()["status"] == "claimed"


def test_new_staff_can_view_shows_passes_and_queues(client, show, trainee):
    shows = client.get("/api/shows", headers=_h(trainee))
    passes = client.get(f"/api/shows/{show.id}/passes", headers=_h(trainee))
    queue = client.get(f"/api/shows/{show.id}/alternates", headers=_h(trainee))
    lottery = client.get(f"/api/shows/{show.id}/lottery", headers=_h(trainee))

    assert shows.status_code == 200
    assert passes.status_code == 200
    assert queue.status_code == 200
    assert lottery.status_code == 200


def test_new_promotions_member_can_do_promotions_work(client, db, show, new_promo):
    venues = client.get("/api/venues", headers=_h(new_promo))
    pickers = client.get("/api/venues/promotions-staff", headers=_h(new_promo))
    create = client.post(
        "/api/venues",
        json={
            "name": "Trainee Venue",
            "address": "2 Trainee St",
            "owner_emails": [new_promo.email],
        },
        headers=_h(new_promo),
    )

    assert venues.status_code == 200
    assert [p["email"] for p in pickers.json()] == [new_promo.email]
    assert create.status_code == 201, create.text
    assert create.json()["owner_emails"] == [new_promo.email]


def test_new_staff_listed_for_specialty_show_owners(client, db, trainee):
    alum = Staff(email="alum@new.test", name="alum", phone="")
    db.add(alum)
    db.commit()

    response = client.get("/api/specialty-shows/staff-emails", headers=_h(trainee))

    assert response.status_code == 200
    assert [s["email"] for s in response.json()] == [trainee.email]
