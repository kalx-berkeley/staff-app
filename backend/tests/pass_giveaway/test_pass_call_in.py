"""Tests for recording that a closed show's passes were called in."""

from datetime import date, datetime, time, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.promoter import Promoter
from app.models.show import Show
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus
from app.models.venue import Venue


@pytest.fixture
def venue(db: Session) -> Venue:
    v = Venue(name="Call Venue", address="1 Call St", track_pass_call_in=True)
    db.add(v)
    db.commit()
    return v


@pytest.fixture
def promo(db: Session) -> Staff:
    staff = Staff(email="pat@call.test", name="Pat", phone="555-0100")
    db.add(staff)
    db.flush()
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.add(StaffDepartment(staff_id=staff.id, department="Promotions"))
    db.commit()
    return staff


def _show(db: Session, venue: Venue, **kwargs) -> Show:
    s = Show(
        event_name="Call Show",
        venue_id=venue.id,
        show_date=kwargs.pop("show_date", date.today() + timedelta(days=30)),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible="yes",
        num_pass_pairs=1,
        status=kwargs.pop("status", "closed"),
        published_at=datetime.now(timezone.utc) - timedelta(days=1),
        **kwargs,
    )
    db.add(s)
    db.commit()
    return s


def _h(staff: Staff) -> dict:
    return {"X-Forwarded-User": staff.email}


def _mark(client, promo: Staff, show: Show):
    return client.post(f"/api/shows/{show.id}/passes-called-in", headers=_h(promo))


def _undo(client, promo: Staff, show: Show):
    return client.delete(f"/api/shows/{show.id}/passes-called-in", headers=_h(promo))


class TestMarking:
    def test_marks_and_audits(self, client, db, venue, promo):
        show = _show(db, venue)

        response = _mark(client, promo, show)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["track_pass_call_in"] is True
        assert body["passes_called_in_at"] is not None
        assert body["passes_called_in_by"] == "Pat"
        audit = db.query(AuditLog).filter_by(event_type="passes_called_in").one()
        assert audit.actor_email == promo.email
        assert audit.entity_id == show.id

    def test_undo_clears_and_audits(self, client, db, venue, promo):
        show = _show(db, venue)
        _mark(client, promo, show)

        response = _undo(client, promo, show)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["passes_called_in_at"] is None
        assert body["passes_called_in_by"] is None
        assert db.query(AuditLog).filter_by(event_type="passes_call_in_undone").one()

    def test_allowed_after_the_show_date(self, client, db, venue, promo):
        show = _show(db, venue, show_date=date.today() - timedelta(days=10))

        assert _mark(client, promo, show).status_code == 200

    @pytest.mark.parametrize("status_", ["draft", "published"])
    def test_refuses_shows_that_are_not_closed(self, client, db, venue, promo, status_):
        show = _show(db, venue, status=status_)

        assert _mark(client, promo, show).status_code == 409
        assert _undo(client, promo, show).status_code == 409

    def test_refuses_when_the_setting_is_off(self, client, db, venue, promo):
        venue.track_pass_call_in = False
        db.commit()
        show = _show(db, venue)

        assert _mark(client, promo, show).status_code == 409

    def test_requires_promotions(self, client, db, venue):
        show = _show(db, venue)
        staff = Staff(email="sam@call.test", name="Sam", phone="555-0101")
        db.add(staff)
        db.flush()
        db.add(StaffStatus(staff_id=staff.id, status="Active"))
        db.commit()

        assert _mark(client, staff, show).status_code == 403


class TestPromotedBy:
    def test_promoter_setting_wins_over_the_venue(self, client, db, venue, promo):
        promoter = Promoter(name="Quiet Promoter", track_pass_call_in=False)
        db.add(promoter)
        db.commit()
        show = _show(db, venue, promoter_id=promoter.id)

        assert _mark(client, promo, show).status_code == 409
        body = client.get(f"/api/shows/{show.id}", headers=_h(promo)).json()
        assert body["track_pass_call_in"] is False

    def test_promoter_can_turn_it_on(self, client, db, venue, promo):
        venue.track_pass_call_in = False
        promoter = Promoter(name="Tracking Promoter", track_pass_call_in=True)
        db.add(promoter)
        db.commit()
        show = _show(db, venue, promoter_id=promoter.id)

        assert _mark(client, promo, show).status_code == 200


class TestLifecycle:
    def test_reopening_clears_the_mark(self, client, db, venue, promo):
        show = _show(db, venue)
        _mark(client, promo, show)

        response = client.post(f"/api/shows/{show.id}/reopen", headers=_h(promo))

        assert response.status_code == 200, response.text
        assert response.json()["passes_called_in_at"] is None
        assert response.json()["passes_called_in_by"] is None

    def test_turning_the_setting_off_keeps_the_mark(self, client, db, venue, promo):
        show = _show(db, venue)
        _mark(client, promo, show)
        venue.track_pass_call_in = False
        db.commit()

        body = client.get(f"/api/shows/{show.id}", headers=_h(promo)).json()

        assert body["track_pass_call_in"] is False
        assert body["passes_called_in_at"] is not None


class TestSetting:
    def test_defaults_to_off(self, client, promo):
        venue = client.post(
            "/api/venues", headers=_h(promo), json={"name": "V", "address": "A"}
        )
        promoter = client.post("/api/promoters", headers=_h(promo), json={"name": "P"})

        assert venue.json()["track_pass_call_in"] is False
        assert promoter.json()["track_pass_call_in"] is False

    @pytest.mark.parametrize(
        "path,payload",
        [("/api/venues", {"name": "V", "address": "A"}), ("/api/promoters", {"name": "P"})],
    )
    def test_round_trips(self, client, promo, path, payload):
        created = client.post(
            path, headers=_h(promo), json={**payload, "track_pass_call_in": True}
        )
        assert created.status_code in (200, 201), created.text
        assert created.json()["track_pass_call_in"] is True

        updated = client.put(
            f"{path}/{created.json()['id']}",
            headers=_h(promo),
            json={"track_pass_call_in": False},
        )
        assert updated.json()["track_pass_call_in"] is False
