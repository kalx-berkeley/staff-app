"""Tests for Talk & Info Shows: specialty shows with category "talk" and staff members."""

from datetime import date, datetime, time, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.pass_model import Pass
from app.models.show import Show
from app.models.specialty_show import SpecialtyShow
from app.models.specialty_show_dj import SpecialtyShowDJ
from app.models.specialty_show_spinitron_show import SpecialtyShowSpinitronShow
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus
from app.models.talk_show_staff import TalkShowStaff
from app.models.venue import Venue
from app.pass_giveaway.services.specialty_show_spinitron import specialty_show_ids
from tests.personas import dj_fields

PROMO = {"X-Forwarded-User": "promo@example.com"}
NEWS = {"X-Forwarded-User": "news@example.com"}
OTHER = {"X-Forwarded-User": "other@example.com"}


def _staff(db: Session, email: str, *statuses: str, department: str | None = None) -> Staff:
    staff = Staff(email=email, name=email.split("@")[0].title(), phone="")
    db.add(staff)
    db.flush()
    for status in statuses:
        db.add(StaffStatus(staff_id=staff.id, status=status))
    if department:
        db.add(StaffDepartment(staff_id=staff.id, department=department))
    db.commit()
    return staff


@pytest.fixture
def promo(db: Session) -> Staff:
    return _staff(db, "promo@example.com", "Active", department="Promotions")


@pytest.fixture
def news(db: Session) -> Staff:
    """A new (🆕) staff member who isn't a DJ, on the talk show's staff."""
    return _staff(db, "news@example.com", "🆕")


@pytest.fixture
def other(db: Session) -> Staff:
    return _staff(db, "other@example.com", "Active")


@pytest.fixture
def talk_show(db: Session, news: Staff) -> SpecialtyShow:
    show = SpecialtyShow(name="Morning Report", category="talk")
    db.add(show)
    db.flush()
    db.add(SpecialtyShowSpinitronShow(specialty_show_id=show.id, spinitron_show_id=555))
    db.add(TalkShowStaff(specialty_show_id=show.id, staff_id=news.id))
    db.commit()
    return show


def _show_with_pair(db: Session, lottery: bool = False) -> tuple[Show, Pass]:
    venue = Venue(name="Talk Venue", address="1 Radio St")
    db.add(venue)
    db.flush()
    show = Show(
        event_name="Talk Test Show",
        venue_id=venue.id,
        show_date=date.today() + timedelta(days=30),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible="yes",
        num_pass_pairs=1,
        status="published",
        lottery_enabled=lottery,
        lottery_window_hours=24,
        published_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db.add(show)
    db.flush()
    pair = Pass(show_id=show.id, pass_type="pair", status="available")
    db.add(pair)
    db.commit()
    return show, pair


def test_promotions_create_a_talk_show(client: TestClient, promo, db: Session, monkeypatch):
    async def resolve(urls):
        from app.pass_giveaway.services.specialty_show_spinitron import ResolvedShow

        return [ResolvedShow(id=777, title="City Desk")]

    monkeypatch.setattr("app.pass_giveaway.routers.specialty_shows.resolve_urls", resolve)
    response = client.post(
        "/api/specialty-shows",
        json={
            "name": "City Desk",
            "category": "talk",
            "spinitron_urls": ["https://spinitron.com/KALX/show/777/"],
        },
        headers=PROMO,
    )
    assert response.status_code == 201, response.text
    assert response.json()["category"] == "talk"
    assert db.query(SpecialtyShow).filter_by(name="City Desk").one().category == "talk"


def test_shows_default_to_music_and_list_by_category(
    client: TestClient, promo, talk_show, db: Session
):
    music = SpecialtyShow(name="Take Five")
    db.add(music)
    db.commit()
    assert music.category == "music"

    names = lambda params: [  # noqa: E731
        s["name"]
        for s in client.get("/api/specialty-shows", params=params, headers=PROMO).json()
    ]
    assert names({}) == ["Morning Report", "Take Five"]
    assert names({"category": "talk"}) == ["Morning Report"]
    assert names({"category": "music"}) == ["Take Five"]


def test_staff_members_are_managed_by_email(
    client: TestClient, promo, talk_show, other: Staff
):
    response = client.put(
        f"/api/specialty-shows/{talk_show.id}",
        json={
            "staff_member_emails": ["news@example.com", "other@example.com", "nobody@x.com"]
        },
        headers=PROMO,
    )
    assert response.status_code == 200, response.text
    assert response.json()["staff_member_emails"] == [
        "news@example.com",
        "other@example.com",
    ]
    assert response.json()["staff_member_details"][1] == {
        "email": "other@example.com",
        "name": "Other",
    }


def test_each_kind_takes_only_its_own_members(
    client: TestClient, promo, talk_show, db: Session
):
    response = client.put(
        f"/api/specialty-shows/{talk_show.id}",
        json={"dj_persona_ids": [123]},
        headers=PROMO,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "A Talk & Info Show has staff members, not DJs"

    music = SpecialtyShow(name="Take Five")
    db.add(music)
    db.flush()
    db.add(SpecialtyShowSpinitronShow(specialty_show_id=music.id, spinitron_show_id=301137))
    db.commit()
    response = client.put(
        f"/api/specialty-shows/{music.id}",
        json={"staff_member_emails": ["news@example.com"]},
        headers=PROMO,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "A Specialty Music Show has DJs, not staff members"


def test_mine_includes_talk_shows_im_on(client: TestClient, talk_show):
    [mine] = client.get("/api/specialty-shows/mine", headers=NEWS).json()
    assert mine["name"] == "Morning Report"
    assert mine["is_staff_member"] is True
    assert mine["is_dj"] is False


def test_a_talk_shows_spinitron_show_isnt_a_dj_shift(db: Session, talk_show):
    assert specialty_show_ids(db) == {555}


def test_staff_members_reserve_passes_without_being_djs(
    client: TestClient, db: Session, talk_show
):
    show, pair = _show_with_pair(db)
    response = client.post(
        f"/api/passes/{pair.id}/preassign/self",
        json={
            "assignment_date": (date.today() + timedelta(days=3)).isoformat(),
            "specialty_show_id": talk_show.id,
        },
        headers=NEWS,
    )
    assert response.status_code == 200, response.text
    db.refresh(pair)
    assert pair.preassigned_to == "Morning Report"
    assert pair.preassigned_specialty_show_id == talk_show.id

    # ...and release them again
    response = client.delete(f"/api/passes/{pair.id}/preassign", headers=NEWS)
    assert response.status_code == 200, response.text
    db.refresh(pair)
    assert pair.preassigned_to is None


def test_other_staff_cant_reserve_for_a_talk_show(
    client: TestClient, db: Session, talk_show, other
):
    show, pair = _show_with_pair(db)
    response = client.post(
        f"/api/passes/{pair.id}/preassign/self",
        json={
            "assignment_date": (date.today() + timedelta(days=3)).isoformat(),
            "specialty_show_id": talk_show.id,
        },
        headers=OTHER,
    )
    assert response.status_code == 403
    assert (
        response.json()["detail"] == "You are not a staff member of this Talk & Info Show"
    )


def test_reserving_under_your_own_name_still_needs_sublist_dj(
    client: TestClient, db: Session, talk_show, news
):
    show, pair = _show_with_pair(db)
    response = client.post(
        f"/api/passes/{pair.id}/preassign/self",
        json={"assignment_date": (date.today() + timedelta(days=3)).isoformat()},
        headers=NEWS,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Only Sublist DJ staff can perform this action"


def test_music_show_membership_still_needs_sublist_dj(client: TestClient, db: Session):
    dj = _staff(db, "dj@example.com", "Active", "Sublist DJ")
    for column, value in dj_fields("DJ Lite").items():
        setattr(dj, column, value)
    music = SpecialtyShow(name="Take Five")
    db.add(music)
    db.flush()
    db.add(SpecialtyShowDJ(specialty_show_id=music.id, persona_id=dj.spinitron_ids[0]))
    db.commit()
    show, pair = _show_with_pair(db)
    body = {
        "assignment_date": (date.today() + timedelta(days=3)).isoformat(),
        "specialty_show_id": music.id,
    }
    response = client.post(
        f"/api/passes/{pair.id}/preassign/self",
        json=body,
        headers={"X-Forwarded-User": "dj@example.com"},
    )
    assert response.status_code == 200, response.text

    # Not a Sublist DJ any more: refused, even though still on the show
    db.query(StaffStatus).filter_by(staff_id=dj.id, status="Sublist DJ").delete()
    db.commit()
    client.delete(f"/api/passes/{pair.id}/preassign", headers=PROMO)
    response = client.post(
        f"/api/passes/{pair.id}/preassign/self",
        json=body,
        headers={"X-Forwarded-User": "dj@example.com"},
    )
    assert response.status_code == 403


def test_staff_members_enter_the_dj_lottery_for_their_show(
    client: TestClient, db: Session, talk_show
):
    show, _ = _show_with_pair(db, lottery=True)
    response = client.post(
        f"/api/shows/{show.id}/lottery/enter/dj",
        json={
            "assignment_date": (date.today() + timedelta(days=3)).isoformat(),
            "specialty_show_id": talk_show.id,
        },
        headers=NEWS,
    )
    assert response.status_code == 201, response.text
    assert response.json()["dj_name"] == "Morning Report"

    response = client.delete(f"/api/shows/{show.id}/lottery/dj_entry", headers=NEWS)
    assert response.status_code == 204, response.text
