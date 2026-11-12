"""Tests for venues that give staff passes for a different date than the pass pairs.

See docs/pass-giveaway/specs/staff-passes-another-date/plan.md.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.pass_model import Pass
from app.models.show import Show
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus
from app.models.venue import Venue


@pytest.fixture
def venue(db: Session) -> Venue:
    v = Venue(name="Split Venue", address="1 Split St", staff_pass_day_offset=1)
    db.add(v)
    db.commit()
    return v


@pytest.fixture
def promo(db: Session) -> Staff:
    staff = Staff(email="pat@split.test", name="Pat", phone="555-0100")
    db.add(staff)
    db.flush()
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.add(StaffDepartment(staff_id=staff.id, department="Promotions"))
    db.commit()
    return staff


@pytest.fixture
def active_staff(db: Session) -> Staff:
    staff = Staff(email="sam@split.test", name="Sam", phone="555-0101")
    db.add(staff)
    db.flush()
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.commit()
    return staff


FRIDAY = date.today() + timedelta(days=30)
SATURDAY = FRIDAY + timedelta(days=1)


def _h(staff: Staff) -> dict:
    return {"X-Forwarded-User": staff.email}


def _split_payload(venue: Venue, **overrides) -> dict:
    payload = {
        "event_name": "Split Show",
        "venue_id": venue.id,
        "show_date": FRIDAY.isoformat(),
        "show_time": "20:00:00",
        "age_restriction": "all_ages",
        "wheelchair_accessible": "yes",
        "num_pass_pairs": 2,
        "staff_pass_adjustment": 1,
        "planned_close_date": (FRIDAY - timedelta(days=2)).isoformat(),
        "planned_close_time": "12:00:00",
        "auto_close": True,
        "staff_instructions": "Ask for Lee",
        "dj_preassign_prohibition_days": 2,
        "staff_show_date": SATURDAY.isoformat(),
        "staff_show_time": "21:00:00",
        "staff_planned_close_date": (SATURDAY - timedelta(days=2)).isoformat(),
        "staff_planned_close_time": "12:00:00",
    }
    return payload | overrides


def _pass_counts(db: Session, show_id: int) -> dict[str, int]:
    passes = db.query(Pass).filter(Pass.show_id == show_id).all()
    counts: dict[str, int] = {}
    for p in passes:
        counts[p.pass_type] = counts.get(p.pass_type, 0) + 1
    return counts


class TestVenueSetting:
    def test_saves_and_returns_offset(self, client: TestClient, promo):
        response = client.post(
            "/api/venues",
            json={"name": "New Venue", "address": "2 St", "staff_pass_day_offset": -2},
            headers=_h(promo),
        )
        assert response.status_code == 201, response.text
        assert response.json()["staff_pass_day_offset"] == -2

    def test_zero_is_saved_as_no_offset(self, client: TestClient, db, promo, venue):
        response = client.put(
            f"/api/venues/{venue.id}",
            json={"staff_pass_day_offset": 0},
            headers=_h(promo),
        )
        assert response.status_code == 200, response.text
        assert response.json()["staff_pass_day_offset"] is None
        db.refresh(venue)
        assert venue.staff_pass_day_offset is None

    def test_offset_is_limited_to_30_days(self, client: TestClient, promo, venue):
        response = client.put(
            f"/api/venues/{venue.id}",
            json={"staff_pass_day_offset": 31},
            headers=_h(promo),
        )
        assert response.status_code == 422


class TestCreateSplit:
    def test_creates_on_air_and_staff_shows(self, client: TestClient, db, promo, venue):
        response = client.post(
            "/api/shows/split", json=_split_payload(venue), headers=_h(promo)
        )

        assert response.status_code == 201, response.text
        body = response.json()
        on_air, staff = body["on_air_show"], body["staff_show"]

        assert on_air["show_date"] == FRIDAY.isoformat()
        assert on_air["show_time"] == "20:00:00"
        assert on_air["num_pass_pairs"] == 2
        assert on_air["num_staff_passes"] == 0
        assert on_air["dj_preassign_prohibition_days"] == 2
        assert _pass_counts(db, on_air["id"]) == {"pair": 2}

        assert staff["show_date"] == SATURDAY.isoformat()
        assert staff["show_time"] == "21:00:00"
        assert staff["planned_close_date"] == (SATURDAY - timedelta(days=2)).isoformat()
        assert staff["num_pass_pairs"] == 0
        assert staff["num_staff_passes"] == 3
        assert staff["dj_preassign_prohibition_days"] is None
        assert staff["staff_instructions"] == "Ask for Lee"
        assert staff["event_name"] == "Split Show"
        assert _pass_counts(db, staff["id"]) == {"staff": 3}

        assert on_air["status"] == staff["status"] == "draft"

    def test_audit_log_links_staff_show_to_on_air_show(
        self, client: TestClient, db, promo, venue
    ):
        body = client.post(
            "/api/shows/split", json=_split_payload(venue), headers=_h(promo)
        ).json()

        events = {
            e.entity_id: e.details
            for e in db.query(AuditLog).filter_by(event_type="show_created").all()
        }
        assert "split_from_show_id" not in events[body["on_air_show"]["id"]]
        assert (
            events[body["staff_show"]["id"]]["split_from_show_id"]
            == body["on_air_show"]["id"]
        )

    def test_tabler_passes_go_on_the_staff_show(self, client: TestClient, promo, venue):
        response = client.post(
            "/api/shows/split",
            json=_split_payload(venue, co_announce=True, num_tabler_passes=2),
            headers=_h(promo),
        )

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["on_air_show"]["co_announce"] is True
        assert body["on_air_show"]["num_tabler_passes"] == 0
        assert body["staff_show"]["co_announce"] is True
        assert body["staff_show"]["num_tabler_passes"] == 2

    def test_entered_winners_go_on_their_shows(
        self, client: TestClient, db, promo, venue, active_staff
    ):
        response = client.post(
            "/api/shows/split",
            json=_split_payload(
                venue,
                on_air_winners=[
                    {"recipient_name": "Lis Tener", "recipient_phone": "510-555-0199"}
                ],
                staff_winners=[{"staff_id": active_staff.id}],
            ),
            headers=_h(promo),
        )

        assert response.status_code == 201, response.text
        body = response.json()
        on_air_given = (
            db.query(Pass)
            .filter_by(show_id=body["on_air_show"]["id"], status="given_away")
            .count()
        )
        staff_claimed = (
            db.query(Pass)
            .filter_by(show_id=body["staff_show"]["id"], staff_id=active_staff.id)
            .count()
        )
        assert on_air_given == 1
        assert staff_claimed == 1

    def test_staff_show_close_after_its_date_creates_nothing(
        self, client: TestClient, db, promo, venue
    ):
        response = client.post(
            "/api/shows/split",
            json=_split_payload(
                venue, staff_planned_close_date=(SATURDAY + timedelta(days=1)).isoformat()
            ),
            headers=_h(promo),
        )

        assert response.status_code == 422
        assert "Staff show" in response.text
        assert db.query(Show).count() == 0

    def test_needs_staff_passes(self, client: TestClient, db, promo, venue):
        response = client.post(
            "/api/shows/split",
            json=_split_payload(venue, staff_pass_adjustment=-2),
            headers=_h(promo),
        )

        assert response.status_code == 422
        assert "at least one staff pass" in response.text
        assert db.query(Show).count() == 0

    def test_multi_day_shows_are_not_split(self, client: TestClient, db, promo, venue):
        response = client.post(
            "/api/shows/split",
            json=_split_payload(
                venue, show_start_date=(FRIDAY - timedelta(days=1)).isoformat()
            ),
            headers=_h(promo),
        )

        assert response.status_code == 422
        assert db.query(Show).count() == 0

    def test_requires_promotions(self, client: TestClient, db, venue, active_staff):
        response = client.post(
            "/api/shows/split", json=_split_payload(venue), headers=_h(active_staff)
        )
        assert response.status_code == 403
        assert db.query(Show).count() == 0


class TestZeroPairShows:
    def _create(self, client: TestClient, promo: Staff, venue: Venue, **overrides):
        payload = {
            "event_name": "Staff Only",
            "venue_id": venue.id,
            "show_date": SATURDAY.isoformat(),
            "show_time": "20:00:00",
            "age_restriction": "all_ages",
            "wheelchair_accessible": "yes",
            "num_pass_pairs": 0,
            "staff_pass_adjustment": 2,
        } | overrides
        return client.post("/api/shows", json=payload, headers=_h(promo))

    def test_show_with_only_staff_passes(self, client: TestClient, db, promo, venue):
        response = self._create(client, promo, venue)

        assert response.status_code == 201, response.text
        assert _pass_counts(db, response.json()["id"]) == {"staff": 2}

    def test_show_needs_at_least_one_pass(self, client: TestClient, promo, venue):
        response = self._create(client, promo, venue, staff_pass_adjustment=0)

        assert response.status_code == 422
        assert "at least one pass pair or staff pass" in response.text

    def test_update_can_not_remove_every_pass(self, client: TestClient, promo, venue):
        show_id = self._create(client, promo, venue).json()["id"]

        response = client.put(
            f"/api/shows/{show_id}",
            json={"staff_pass_adjustment": 0},
            headers=_h(promo),
        )

        assert response.status_code == 422
        assert "at least one pass pair or staff pass" in response.text

    def test_at_most_15_staff_passes(self, client: TestClient, promo, venue):
        response = self._create(client, promo, venue, staff_pass_adjustment=16)
        assert response.status_code == 422

        response = self._create(client, promo, venue, staff_pass_adjustment=15)
        assert response.status_code == 201, response.text
