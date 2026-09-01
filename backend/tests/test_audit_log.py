"""Tests for the audit logging system."""

import pytest
from datetime import date, time, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.venue import Venue
from app.models.show import Show
from app.models.pass_model import Pass
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus
from app.models.on_air_winner import OnAirWinner
from app.services import audit_service
from app.services.pass_service import PassService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def venue(db: Session):
    v = Venue(name="Audit Venue", address="1 Audit St", win_frequency_days=30)
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


@pytest.fixture
def promotions_staff(db: Session):
    staff = Staff(email="promo@audit.test", name="Promo User", phone="555-1111")
    db.add(staff)
    db.flush()
    db.add(StaffDepartment(staff_id=staff.id, department="Promotions"))
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.commit()
    db.refresh(staff)
    return staff


@pytest.fixture
def staff_member(db: Session):
    staff = Staff(email="staff@audit.test", name="Staff User", phone="555-2222")
    db.add(staff)
    db.flush()
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.commit()
    db.refresh(staff)
    return staff


@pytest.fixture
def published_show(db: Session, venue, promotions_staff):
    show = Show(
        event_name="Audit Show",
        venue_id=venue.id,
        show_date=date(2025, 6, 1),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible=True,
        num_pass_pairs=2,
        status="published",
    )
    db.add(show)
    db.commit()
    db.refresh(show)
    for _ in range(2):
        db.add(Pass(show_id=show.id, pass_type="pair", status="available"))
    for _ in range(2):
        db.add(Pass(show_id=show.id, pass_type="staff", status="available"))
    db.commit()
    return show


# ---------------------------------------------------------------------------
# Unit tests: audit_service.log_event
# ---------------------------------------------------------------------------


def test_log_event_creates_row(db: Session):
    audit_service.log_event(
        db,
        event_type="test_event",
        actor_email="user@example.com",
        actor_role="promotions",
        entity_type="show",
        entity_id=42,
        details={"foo": "bar"},
    )
    row = db.query(AuditLog).filter(AuditLog.event_type == "test_event").first()
    assert row is not None
    assert row.actor_email == "user@example.com"
    assert row.entity_id == 42
    assert row.details == {"foo": "bar"}


def test_log_event_does_not_raise_on_bad_db(db: Session, monkeypatch):
    """A failure inside log_event must not propagate to the caller."""

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated db error")

    monkeypatch.setattr(db, "add", _boom)
    # Should not raise
    audit_service.log_event(db, event_type="will_fail")


# ---------------------------------------------------------------------------
# Integration: pass giveaway creates audit entry
# ---------------------------------------------------------------------------


def test_pass_giveaway_audit(
    client: TestClient, db: Session, published_show, promotions_staff
):
    pair_pass = (
        db.query(Pass)
        .filter(Pass.show_id == published_show.id, Pass.pass_type == "pair")
        .first()
    )
    response = client.post(
        f"/api/passes/{pair_pass.id}/giveaway",
        json={
            "recipient_name": "Alice",
            "recipient_phone": "555-0001",
            "given_away_by_dj": "DJ Test",
        },
        headers={"X-Forwarded-User": promotions_staff.email},
    )
    assert response.status_code == 200

    row = db.query(AuditLog).filter(AuditLog.event_type == "pass_given_away").first()
    assert row is not None
    assert row.entity_id == pair_pass.id
    assert row.details["dj"] == "DJ Test"
    assert row.details["recipient_name"] == "Alice"


# ---------------------------------------------------------------------------
# Integration: scheduler expiry creates audit entry
# ---------------------------------------------------------------------------


def test_preassignment_expiry_audit(db: Session, published_show):
    pair_pass = (
        db.query(Pass)
        .filter(Pass.show_id == published_show.id, Pass.pass_type == "pair")
        .first()
    )
    today = date.today()
    pair_pass.preassigned_dj = "DJ Stale"
    pair_pass.preassigned_date = today - timedelta(days=1)
    db.commit()

    PassService.expire_stale_preassignments(db, _today=today)

    row = db.query(AuditLog).filter(AuditLog.event_type == "preassignment_expired").first()
    assert row is not None
    assert row.entity_id == pair_pass.id
    assert row.details["dj"] == "DJ Stale"


# ---------------------------------------------------------------------------
# Integration: admin audit-log endpoint with filtering
# ---------------------------------------------------------------------------


def test_admin_audit_log_endpoint(client: TestClient, db: Session, promotions_staff):
    # Write a couple of entries directly
    audit_service.log_event(
        db,
        event_type="show_created",
        actor_email=promotions_staff.email,
        actor_role="promotions",
        entity_type="show",
        entity_id=1,
    )
    audit_service.log_event(
        db,
        event_type="venue_created",
        actor_email=promotions_staff.email,
        actor_role="promotions",
        entity_type="venue",
        entity_id=2,
    )

    response = client.get(
        "/api/admin/audit-log",
        headers={"X-Forwarded-User": promotions_staff.email},
    )
    assert response.status_code == 200
    items = response.json()
    assert len(items) >= 2

    # Filter by event_type
    response = client.get(
        "/api/admin/audit-log?event_type=show_created",
        headers={"X-Forwarded-User": promotions_staff.email},
    )
    assert response.status_code == 200
    items = response.json()
    assert all(i["event_type"] == "show_created" for i in items)


# ---------------------------------------------------------------------------
# Integration: pass claim and release audit entries
# ---------------------------------------------------------------------------


def test_pass_claim_audit(client: TestClient, db: Session, published_show, staff_member):
    staff_pass = (
        db.query(Pass)
        .filter(Pass.show_id == published_show.id, Pass.pass_type == "staff")
        .first()
    )
    response = client.post(
        f"/api/passes/{staff_pass.id}/claim",
        headers={"X-Forwarded-User": staff_member.email},
    )
    assert response.status_code == 200

    row = db.query(AuditLog).filter(AuditLog.event_type == "pass_claimed").first()
    assert row is not None
    assert row.entity_id == staff_pass.id
    assert row.actor_email == staff_member.email


def test_pass_release_audit(client: TestClient, db: Session, published_show, staff_member):
    staff_pass = (
        db.query(Pass)
        .filter(Pass.show_id == published_show.id, Pass.pass_type == "staff")
        .first()
    )
    staff_pass.status = "claimed"
    staff_pass.staff_id = staff_member.id
    db.commit()

    response = client.delete(
        f"/api/passes/{staff_pass.id}/claim",
        headers={"X-Forwarded-User": staff_member.email},
    )
    assert response.status_code == 200

    row = db.query(AuditLog).filter(AuditLog.event_type == "pass_released").first()
    assert row is not None
    assert row.entity_id == staff_pass.id


# ---------------------------------------------------------------------------
# Integration: venue frequency override and warning
# ---------------------------------------------------------------------------


def test_winner_frequency_warning_audit(
    client: TestClient, db: Session, published_show, promotions_staff, venue
):
    # Create a previous win for the same phone at this venue
    pair_pass = (
        db.query(Pass)
        .filter(Pass.show_id == published_show.id, Pass.pass_type == "pair")
        .first()
    )
    pair_pass.status = "given_away"
    pair_pass.given_away_by_dj = "DJ Old"
    db.flush()
    db.add(
        OnAirWinner(
            pass_id=pair_pass.id,
            venue_id=venue.id,
            show_id=published_show.id,
            recipient_name="Bob",
            recipient_phone="5559999",
            given_away_by_dj="DJ Old",
        )
    )
    db.commit()

    # New show at same venue (within 30 days)
    new_show = Show(
        event_name="New Show",
        venue_id=venue.id,
        show_date=date(2025, 6, 10),  # 9 days after first show
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible=True,
        num_pass_pairs=1,
        status="published",
    )
    db.add(new_show)
    db.commit()
    db.refresh(new_show)

    response = client.get(
        f"/api/venues/{venue.id}/check-winner",
        params={"phone": "555-9999", "show_id": new_show.id},
        headers={"X-Forwarded-User": promotions_staff.email},
    )
    assert response.status_code == 200
    assert response.json()["eligible"] is False

    row = (
        db.query(AuditLog).filter(AuditLog.event_type == "winner_frequency_warning").first()
    )
    assert row is not None
    assert row.details["recipient_phone"] == "555-9999"


# ---------------------------------------------------------------------------
# Integration: show update creates audit entry
# ---------------------------------------------------------------------------


def test_show_update_audit(
    client: TestClient, db: Session, published_show, promotions_staff
):
    response = client.put(
        f"/api/shows/{published_show.id}",
        json={"event_name": "Updated Show Name"},
        headers={"X-Forwarded-User": promotions_staff.email},
    )
    assert response.status_code == 200

    row = db.query(AuditLog).filter(AuditLog.event_type == "show_updated").first()
    assert row is not None
    assert row.entity_id == published_show.id
    assert row.actor_email == promotions_staff.email
    assert "event_name" in row.details["changed_fields"]
    assert row.details["changed_fields"]["event_name"]["after"] == "Updated Show Name"


# ---------------------------------------------------------------------------
# Integration: preassignment removal creates audit entry
# ---------------------------------------------------------------------------


def test_preassignment_removal_audit(
    client: TestClient, db: Session, published_show, promotions_staff
):
    pair_pass = (
        db.query(Pass)
        .filter(Pass.show_id == published_show.id, Pass.pass_type == "pair")
        .first()
    )
    pair_pass.preassigned_dj = "DJ Preset"
    pair_pass.preassigned_date = date(2025, 6, 1)
    db.commit()

    response = client.delete(
        f"/api/passes/{pair_pass.id}/preassign",
        headers={"X-Forwarded-User": promotions_staff.email},
    )
    assert response.status_code == 200

    row = (
        db.query(AuditLog)
        .filter(AuditLog.event_type == "pass_preassignment_removed")
        .first()
    )
    assert row is not None
    assert row.entity_id == pair_pass.id
    assert row.actor_email == promotions_staff.email
    assert row.actor_role == "promotions"
    assert row.details["prior_dj"] == "DJ Preset"


# ---------------------------------------------------------------------------
# Integration: notification preferences update creates audit entry
# ---------------------------------------------------------------------------


def test_notification_preferences_update_audit(
    client: TestClient, db: Session, staff_member
):
    response = client.put(
        "/api/users/notification-preferences",
        json={"email_enabled": False},
        headers={"X-Forwarded-User": staff_member.email},
    )
    assert response.status_code == 200

    row = (
        db.query(AuditLog)
        .filter(AuditLog.event_type == "notification_preferences_updated")
        .first()
    )
    assert row is not None
    assert row.actor_email == staff_member.email
    assert row.details["email_enabled"] is False
