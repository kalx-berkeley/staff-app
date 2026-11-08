"""Tests for winners a promotions rep enters on the New Show and Edit Show forms.

See docs/pass-giveaway/specs/preassigned-winners/plan.md.
"""

from datetime import date, datetime, time, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.lottery_entry import LotteryEntry
from app.models.on_air_winner import OnAirWinner
from app.models.pass_model import Pass
from app.models.show import Show
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_pass_alternate import StaffPassAlternate
from app.models.staff_status import StaffStatus
from app.models.venue import Venue

SEND_EMAIL = "app.common.services.notification_service.send_email"
SHOW_DATE = "2099-12-31"


def _staff(db: Session, email: str, status: str = "Active", **fields) -> Staff:
    staff = Staff(email=email, name=email.split("@")[0].title(), phone="555-0100", **fields)
    db.add(staff)
    db.flush()
    db.add(StaffStatus(staff_id=staff.id, status=status))
    db.commit()
    return staff


@pytest.fixture
def rep(db: Session) -> Staff:
    staff = _staff(db, "rep@test.com")
    db.add(StaffDepartment(staff_id=staff.id, department="Promotions"))
    db.commit()
    return staff


@pytest.fixture
def venue(db: Session) -> Venue:
    venue = Venue(name="Test Venue", address="1 Main St")
    db.add(venue)
    db.commit()
    return venue


def _headers(rep: Staff) -> dict:
    return {"X-Forwarded-User": rep.email}


def _show_body(venue: Venue, **fields) -> dict:
    return {
        "event_name": "Replacement Show",
        "venue_id": venue.id,
        "show_date": SHOW_DATE,
        "show_time": "20:00:00",
        "age_restriction": "all_ages",
        "wheelchair_accessible": "yes",
        "num_pass_pairs": 2,
        **fields,
    }


WINNER = {"recipient_name": "Caller One", "recipient_phone": "(510) 555-1234"}


def _passes(db: Session, show_id: int, pass_type: str) -> list[Pass]:
    return (
        db.query(Pass)
        .filter(Pass.show_id == show_id, Pass.pass_type == pass_type)
        .order_by(Pass.id)
        .all()
    )


def _existing_show(db: Session, venue: Venue, status: str = "published") -> Show:
    """A show with 2 pass pairs (the first reserved for a DJ) and 3 staff passes."""
    show = Show(
        event_name="Existing Show",
        venue_id=venue.id,
        show_date=date(2099, 12, 31),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible="yes",
        num_pass_pairs=2,
        staff_pass_adjustment=1,
        status=status,
    )
    db.add(show)
    db.flush()
    db.add(Pass(show_id=show.id, pass_type="pair", preassigned_dj="DJ Reserved"))
    db.add(Pass(show_id=show.id, pass_type="pair"))
    for _ in range(3):
        db.add(Pass(show_id=show.id, pass_type="staff"))
    db.commit()
    return show


class TestNewShow:
    def test_winners_and_claims_go_on_the_new_show(
        self, client: TestClient, db: Session, rep: Staff, venue: Venue
    ):
        ann = _staff(db, "ann@test.com")
        ben = _staff(db, "ben@test.com")
        body = _show_body(
            venue,
            on_air_winners=[{**WINNER, "given_away_by_dj": "DJ Night"}, WINNER],
            staff_winners=[
                {"staff_id": ann.id, "has_guest": True, "guest_name": "Pal"},
                {"staff_id": ben.id},
            ],
            staff_pass_adjustment=1,
        )

        with patch(SEND_EMAIL) as mock_send:
            response = client.post("/api/shows", json=body, headers=_headers(rep))

        assert response.status_code == 201, response.text
        mock_send.assert_not_called()
        show_id = response.json()["id"]
        pairs = _passes(db, show_id, "pair")
        assert [p.status for p in pairs] == ["given_away", "given_away"]
        assert [p.given_away_by_dj for p in pairs] == ["DJ Night", "Unknown"]
        winners = db.query(OnAirWinner).filter(OnAirWinner.show_id == show_id).all()
        assert {w.recipient_phone for w in winners} == {"5105551234"}

        staff = _passes(db, show_id, "staff")
        ann_pass = next(p for p in staff if p.staff_id == ann.id and not p.guest_of_pass_id)
        assert ann_pass.has_guest and ann_pass.guest_name == "Pal"
        assert any(p.guest_of_pass_id == ann_pass.id for p in staff)
        assert any(p.staff_id == ben.id for p in staff)
        assert all(p.status == "claimed" for p in staff)

        events = [a.event_type for a in db.query(AuditLog).all()]
        assert events.count("on_air_winner_entered_by_promotions") == 2
        assert events.count("staff_pass_assigned_by_promotions") == 2

    def test_venue_win_frequency_limit_is_skipped(
        self, client: TestClient, db: Session, rep: Staff, venue: Venue
    ):
        venue.win_frequency_days = 365
        old = _existing_show(db, venue)
        old_pair = _passes(db, old.id, "pair")[1]
        old_pair.status = "given_away"
        db.add(
            OnAirWinner(
                pass_id=old_pair.id,
                venue_id=venue.id,
                show_id=old.id,
                recipient_name="Caller One",
                recipient_phone="5105551234",
                given_away_by_dj="DJ",
                created_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

        response = client.post(
            "/api/shows",
            json=_show_body(venue, on_air_winners=[WINNER]),
            headers=_headers(rep),
        )

        assert response.status_code == 201, response.text

    @pytest.mark.parametrize(
        "make_body, detail",
        [
            (
                lambda s: {"staff_winners": [{"staff_id": s["new"].id}]},
                "isn't Active staff",
            ),
            (
                lambda s: {"staff_winners": [{"staff_id": s["away"].id}]},
                "on leave of absence",
            ),
            (
                lambda s: {
                    "staff_winners": [{"staff_id": s["ann"].id}, {"staff_id": s["ann"].id}]
                },
                "more than once",
            ),
            (
                lambda s: {"on_air_winners": [WINNER, WINNER, WINNER]},
                "1 more free pass pair",
            ),
            (
                lambda s: {
                    "staff_winners": [{"staff_id": s["ann"].id, "has_guest": True}],
                    "staff_pass_adjustment": -1,
                },
                "1 more free staff pass",
            ),
        ],
    )
    def test_a_bad_row_saves_nothing(
        self,
        client: TestClient,
        db: Session,
        rep: Staff,
        venue: Venue,
        make_body,
        detail,
    ):
        people = {
            "ann": _staff(db, "ann@test.com"),
            "new": _staff(db, "new@test.com", status="🆕"),
            "away": _staff(
                db, "away@test.com", loa_start=date(2099, 1, 1), loa_end=date(2100, 1, 1)
            ),
        }

        response = client.post(
            "/api/shows", json=_show_body(venue, **make_body(people)), headers=_headers(rep)
        )

        assert response.status_code == 422
        assert detail in response.json()["detail"]
        assert db.query(Show).count() == 0

    def test_venue_guest_list_rules_apply(
        self, client: TestClient, db: Session, rep: Staff, venue: Venue
    ):
        venue.email_address_requirement = "all"
        venue.staff_guest_requires_name = True
        db.commit()
        ann = _staff(db, "ann@test.com")

        no_email = client.post(
            "/api/shows",
            json=_show_body(venue, on_air_winners=[WINNER]),
            headers=_headers(rep),
        )
        no_guest_name = client.post(
            "/api/shows",
            json=_show_body(venue, staff_winners=[{"staff_id": ann.id, "has_guest": True}]),
            headers=_headers(rep),
        )

        assert no_email.status_code == 422
        assert "email address" in no_email.json()["detail"]
        assert no_guest_name.status_code == 422
        assert "+1 guest" in no_guest_name.json()["detail"]
        assert db.query(Show).count() == 0


class TestEditShow:
    def test_dj_reserved_pairs_are_never_filled(
        self, client: TestClient, db: Session, rep: Staff, venue: Venue
    ):
        show = _existing_show(db, venue)

        two = client.put(
            f"/api/shows/{show.id}",
            json={"on_air_winners": [WINNER, WINNER]},
            headers=_headers(rep),
        )
        one = client.put(
            f"/api/shows/{show.id}",
            json={"on_air_winners": [WINNER]},
            headers=_headers(rep),
        )

        assert two.status_code == 422
        assert one.status_code == 200, one.text
        reserved, free = _passes(db, show.id, "pair")
        assert reserved.status == "available" and reserved.preassigned_dj == "DJ Reserved"
        assert free.status == "given_away"

    def test_raising_the_pass_count_in_the_same_save_makes_room(
        self, client: TestClient, db: Session, rep: Staff, venue: Venue
    ):
        show = _existing_show(db, venue)

        response = client.put(
            f"/api/shows/{show.id}",
            json={"num_pass_pairs": 3, "on_air_winners": [WINNER, WINNER]},
            headers=_headers(rep),
        )

        assert response.status_code == 200, response.text
        statuses = [p.status for p in _passes(db, show.id, "pair")]
        assert statuses.count("given_away") == 2

    def test_someone_who_already_holds_a_pass_is_refused(
        self, client: TestClient, db: Session, rep: Staff, venue: Venue
    ):
        show = _existing_show(db, venue)
        ann = _staff(db, "ann@test.com")
        held = _passes(db, show.id, "staff")[0]
        held.status, held.staff_id = "claimed", ann.id
        db.commit()

        response = client.put(
            f"/api/shows/{show.id}",
            json={"staff_winners": [{"staff_id": ann.id}]},
            headers=_headers(rep),
        )

        assert response.status_code == 422
        assert "already has a staff pass" in response.json()["detail"]

    def test_alternate_place_and_lottery_entry_end_without_email(
        self, client: TestClient, db: Session, rep: Staff, venue: Venue
    ):
        show = _existing_show(db, venue)
        ann = _staff(db, "ann@test.com")
        ben = _staff(db, "ben@test.com")
        now = datetime.now(timezone.utc)
        db.add(StaffPassAlternate(show_id=show.id, staff_id=ann.id, priority_at=now))
        db.add(LotteryEntry(show_id=show.id, entry_type="staff", staff_id=ben.id))
        db.commit()

        with patch(SEND_EMAIL) as mock_send:
            response = client.put(
                f"/api/shows/{show.id}",
                json={"staff_winners": [{"staff_id": ann.id}, {"staff_id": ben.id}]},
                headers=_headers(rep),
            )

        assert response.status_code == 200, response.text
        mock_send.assert_not_called()
        alternate = db.query(StaffPassAlternate).one()
        assert alternate.status == "left"
        assert db.query(LotteryEntry).count() == 0
        claimed = {
            p.staff_id for p in _passes(db, show.id, "staff") if p.status == "claimed"
        }
        assert claimed == {ann.id, ben.id}

    def test_closed_show_is_refused(
        self, client: TestClient, db: Session, rep: Staff, venue: Venue
    ):
        show = _existing_show(db, venue, status="closed")

        response = client.put(
            f"/api/shows/{show.id}",
            json={"on_air_winners": [WINNER]},
            headers=_headers(rep),
        )

        assert response.status_code == 422
        assert "closed show" in response.json()["detail"]
        assert all(p.status == "available" for p in _passes(db, show.id, "pair"))


def test_staff_picker_lists_only_active_staff(client: TestClient, db: Session, rep: Staff):
    _staff(db, "ann@test.com")
    _staff(db, "new@test.com", status="🆕")
    _staff(db, "gone@test.com", status="Inactive")

    response = client.get("/api/shows/staff-pass-claimants", headers=_headers(rep))

    assert response.status_code == 200
    assert [s["email"] for s in response.json()] == ["ann@test.com", "rep@test.com"]


def test_staff_picker_is_for_promotions_only(client: TestClient, db: Session):
    ann = _staff(db, "ann@test.com")

    response = client.get("/api/shows/staff-pass-claimants", headers=_headers(ann))

    assert response.status_code == 403
