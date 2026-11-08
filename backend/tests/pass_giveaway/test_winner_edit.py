"""Tests for the on-air DJ correcting a pass pair winner's details."""

from datetime import date, datetime, time, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.common.areas import PASS_GIVEAWAY_AREA
from app.models.audit_log import AuditLog
from app.models.pass_model import Pass
from app.models.show import Show
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus
from app.models.venue import Venue
from app.pass_giveaway.schemas.pass_schema import GiveawayData
from app.pass_giveaway.services.pass_service import PassService

DJ_STUDIO = {"X-Forwarded-For": "192.168.1.100"}  # in the default dj_studio_network


@pytest.fixture
def venue(db: Session):
    venue = Venue(name="Test Venue", address="123 Test St")
    db.add(venue)
    db.commit()
    return venue


def _make_show(db: Session, venue: Venue, show_date: date, **kwargs) -> Show:
    show = Show(
        event_name=kwargs.pop("event_name", "Test Show"),
        genre=["Rock"],
        venue_id=venue.id,
        show_date=show_date,
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible="yes",
        num_pass_pairs=2,
        status="published",
        **kwargs,
    )
    db.add(show)
    db.flush()
    for _ in range(2):
        db.add(Pass(show_id=show.id, pass_type="pair", status="available"))
    db.commit()
    return show


@pytest.fixture
def show(db: Session, venue):
    return _make_show(db, venue, date(2099, 12, 31))


def _give_away(db: Session, show: Show, phone="510-555-0100", dj="DJ Test") -> Pass:
    pass_item = (
        db.query(Pass).filter(Pass.show_id == show.id, Pass.status == "available").first()
    )
    return PassService.give_away_pass_pair(
        db,
        pass_item.id,
        GiveawayData(
            recipient_name="Jnae Winner",
            recipient_phone=phone,
            recipient_email="jnae@example.com",
            given_away_by_dj=dj,
        ),
    )


@pytest.fixture
def given_away(db: Session, show):
    return _give_away(db, show)


def _edit(client: TestClient, pass_id: int, **overrides):
    body = {
        "recipient_name": "Jane Winner",
        "recipient_phone": "(510) 555-0101",
        "recipient_email": "jane@example.com",
        "given_away_by_dj": "DJ Test",
        **overrides,
    }
    return client.patch(f"/api/passes/{pass_id}/winner", json=body, headers=DJ_STUDIO)


def test_dj_corrects_their_winner(client, db, given_away):
    response = _edit(client, given_away.id)

    assert response.status_code == 200
    data = response.json()
    assert data["recipient_name"] == "Jane Winner"
    assert data["recipient_phone"] == "5105550101"
    db.refresh(given_away)
    assert given_away.on_air_winner.recipient_email == "jane@example.com"


def test_correction_is_audit_logged_with_before_and_after(client, db, given_away):
    _edit(client, given_away.id)

    entry = db.query(AuditLog).filter(AuditLog.event_type == "on_air_winner_updated").one()
    assert entry.area == PASS_GIVEAWAY_AREA
    assert entry.entity_id == given_away.id
    assert entry.details["dj"] == "DJ Test"
    assert entry.details["before"] == {
        "recipient_name": "Jnae Winner",
        "recipient_phone": "5105550100",
        "recipient_email": "jnae@example.com",
    }
    assert entry.details["after"] == {
        "recipient_name": "Jane Winner",
        "recipient_phone": "5105550101",
        "recipient_email": "jane@example.com",
    }


def test_dj_can_correct_any_number_of_times(client, db, given_away):
    assert _edit(client, given_away.id).status_code == 200
    assert _edit(client, given_away.id, recipient_name="Jane Q. Winner").status_code == 200

    assert (
        db.query(AuditLog).filter(AuditLog.event_type == "on_air_winner_updated").count()
        == 2
    )


def test_dj_name_matches_ignoring_case_and_spaces(client, given_away):
    response = _edit(client, given_away.id, given_away_by_dj="  dj test ")

    assert response.status_code == 200


def test_another_dj_cannot_correct_the_winner(client, db, given_away):
    response = _edit(client, given_away.id, given_away_by_dj="DJ Other")

    assert response.status_code == 403
    db.refresh(given_away)
    assert given_away.on_air_winner.recipient_name == "Jnae Winner"


def test_cannot_correct_after_four_hours(client, db, given_away):
    given_away.given_away_at = datetime.now(timezone.utc) - timedelta(hours=4, minutes=1)
    db.commit()

    response = _edit(client, given_away.id)

    assert response.status_code == 403
    assert "4 hours" in response.json()["detail"]


def test_can_correct_just_inside_four_hours(client, db, given_away):
    given_away.given_away_at = datetime.now(timezone.utc) - timedelta(hours=3, minutes=59)
    db.commit()

    assert _edit(client, given_away.id).status_code == 200


def test_cannot_correct_for_a_closed_show(client, db, show, given_away):
    show.status = "closed"
    db.commit()

    assert _edit(client, given_away.id).status_code == 400


def test_cannot_correct_after_the_planned_close_time(client, db, show, given_away):
    show.planned_close_date = date.today() - timedelta(days=1)
    show.planned_close_time = time(12, 0)
    db.commit()

    response = _edit(client, given_away.id)

    assert response.status_code == 400
    assert "planned close" in response.json()["detail"]


def test_cannot_correct_an_available_pass(client, db, show):
    available = db.query(Pass).filter(Pass.show_id == show.id).first()

    assert _edit(client, available.id).status_code == 404


def test_cannot_clear_the_email_when_the_venue_requires_one(client, db, venue, given_away):
    venue.email_address_requirement = "all"
    db.commit()

    response = _edit(client, given_away.id, recipient_email="  ")

    assert response.status_code == 400
    db.refresh(given_away)
    assert given_away.on_air_winner.recipient_email == "jnae@example.com"


def test_can_clear_the_email_when_the_venue_does_not_require_one(client, db, given_away):
    response = _edit(client, given_away.id, recipient_email="")

    assert response.status_code == 200
    db.refresh(given_away)
    assert given_away.on_air_winner.recipient_email is None


def test_promotions_staff_off_the_dj_network_cannot_correct(client, db, given_away):
    staff = Staff(email="promotions@test.com", name="Promo", phone="555-0001")
    db.add(staff)
    db.flush()
    db.add_all([
        StaffDepartment(staff_id=staff.id, department="Promotions"),
        StaffStatus(staff_id=staff.id, status="Active"),
    ])
    db.commit()

    response = client.patch(
        f"/api/passes/{given_away.id}/winner",
        json={
            "recipient_name": "Jane Winner",
            "recipient_phone": "510-555-0101",
            "given_away_by_dj": "DJ Test",
        },
        headers={"X-Forwarded-User": staff.email},
    )

    assert response.status_code == 401


def test_get_winner_returns_the_email_to_the_dj(client, given_away):
    response = client.get(
        f"/api/passes/{given_away.id}/winner",
        params={"dj_name": "DJ Test"},
        headers={**DJ_STUDIO, "X-DJ-Network": "1"},
    )

    assert response.status_code == 200
    assert response.json()["recipient_email"] == "jnae@example.com"


def test_get_winner_refuses_another_dj(client, given_away):
    response = client.get(
        f"/api/passes/{given_away.id}/winner",
        params={"dj_name": "DJ Other"},
        headers=DJ_STUDIO,
    )

    assert response.status_code == 403


def test_get_winner_refuses_after_four_hours(client, db, given_away):
    given_away.given_away_at = datetime.now(timezone.utc) - timedelta(hours=5)
    db.commit()

    response = client.get(
        f"/api/passes/{given_away.id}/winner",
        params={"dj_name": "DJ Test"},
        headers=DJ_STUDIO,
    )

    assert response.status_code == 403


@pytest.fixture
def limited_venue_with_recent_winner(db: Session, venue):
    """A 30-day win limit, and a caller (510-555-0199) who won a week earlier."""
    venue.win_frequency_days = 30
    db.commit()
    earlier = _make_show(db, venue, date(2099, 12, 24), event_name="Earlier Show")
    _give_away(db, earlier, phone="510-555-0199", dj="DJ Earlier")


def test_new_phone_that_won_recently_logs_an_override(
    client, db, given_away, limited_venue_with_recent_winner
):
    response = _edit(client, given_away.id, recipient_phone="510-555-0199")

    assert response.status_code == 200
    override = (
        db.query(AuditLog).filter(AuditLog.event_type == "venue_frequency_override").one()
    )
    assert override.details["winner_edit"] is True
    assert override.details["last_win_show"] == "Earlier Show"
    assert override.details["days_since_last_win"] == 7


def test_unchanged_phone_does_not_count_its_own_win(
    client, db, given_away, limited_venue_with_recent_winner
):
    response = _edit(client, given_away.id, recipient_phone="510-555-0100")

    assert response.status_code == 200
    assert (
        db.query(AuditLog).filter(AuditLog.event_type == "venue_frequency_override").count()
        == 0
    )


def test_check_winner_can_ignore_the_pass_being_corrected(client, db, show, venue):
    venue.win_frequency_days = 30
    db.commit()
    corrected = _give_away(db, show, phone="510-555-0177")

    params = {"phone": "510-555-0177", "show_id": show.id}
    url = f"/api/venues/{venue.id}/check-winner"
    counted = client.get(url, params=params, headers=DJ_STUDIO).json()
    ignored = client.get(
        url, params={**params, "exclude_pass_id": corrected.id}, headers=DJ_STUDIO
    ).json()

    assert counted["eligible"] is False
    assert ignored["eligible"] is True
