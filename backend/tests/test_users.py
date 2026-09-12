"""Tests for user profile management."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus
from app.models.notification_preferences import NotificationPreferences


def _make_promotions_staff(db: Session, email: str, name: str, phone: str) -> Staff:
    """Create a staff member with Promotions department and Active status."""
    staff = Staff(email=email, name=name, phone=phone)
    db.add(staff)
    db.flush()
    db.add(StaffDepartment(staff_id=staff.id, department="Promotions"))
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.commit()
    return staff


def _make_active_staff(db: Session, email: str, name: str, phone: str) -> Staff:
    """Create a staff member with Active status but no Promotions department."""
    staff = Staff(email=email, name=name, phone=phone)
    db.add(staff)
    db.flush()
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.commit()
    return staff


def test_get_current_user_promotions_via_department(client: TestClient, db: Session):
    """Promotions department + Active status → role=promotions."""
    _make_promotions_staff(db, "promo@example.com", "Promo User", "555-1234")

    response = client.get(
        "/api/users/me", headers={"X-Forwarded-User": "promo@example.com"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "promo@example.com"
    assert data["role"] == "promotions"
    assert data["is_dj_network"] is False
    assert data["profile"]["name"] == "Promo User"
    assert data["profile"]["phone"] == "555-1234"


def test_get_current_user_promotions_who_is_also_sublist_dj(
    client: TestClient, db: Session
):
    """A promotions-role staff member who also holds Sublist DJ status must still
    see is_sublist_dj=True on their profile, even though role resolves to
    'promotions' rather than 'staff'."""
    staff = _make_promotions_staff(db, "promo-dj@example.com", "Promo DJ User", "555-1234")
    db.add(StaffStatus(staff_id=staff.id, status="Sublist DJ"))
    db.commit()

    response = client.get(
        "/api/users/me", headers={"X-Forwarded-User": "promo-dj@example.com"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "promotions"
    assert data["profile"]["is_sublist_dj"] is True


def test_get_current_user_promotions_via_paid_staff_status(client: TestClient, db: Session):
    """'Paid Staff' + 'Active' statuses → role=promotions, regardless of department."""
    staff = Staff(email="paid@example.com", name="Paid Staff User", phone="555-9999")
    db.add(staff)
    db.flush()
    db.add(StaffStatus(staff_id=staff.id, status="Paid Staff"))
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.commit()

    response = client.get("/api/users/me", headers={"X-Forwarded-User": "paid@example.com"})

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "paid@example.com"
    assert data["role"] == "promotions"


def test_paid_staff_without_active_is_not_promotions(client: TestClient, db: Session):
    """'Paid Staff' status alone (without 'Active') does not grant promotions role."""
    staff = Staff(email="paid@example.com", name="Paid Staff User", phone="555-9999")
    db.add(staff)
    db.flush()
    db.add(StaffStatus(staff_id=staff.id, status="Paid Staff"))
    db.commit()

    response = client.get("/api/users/me", headers={"X-Forwarded-User": "paid@example.com"})

    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "unauthorized"


def test_promotions_department_without_active_is_not_promotions(
    client: TestClient, db: Session
):
    """Promotions department without 'Active' status does not grant promotions role."""
    staff = Staff(email="promo@example.com", name="Promo User", phone="555-1234")
    db.add(staff)
    db.flush()
    db.add(StaffDepartment(staff_id=staff.id, department="Promotions"))
    db.commit()

    response = client.get(
        "/api/users/me", headers={"X-Forwarded-User": "promo@example.com"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "unauthorized"


def test_get_current_user_staff(client: TestClient, db: Session):
    """Active status (no Promotions dept, no Paid Staff) → role=staff."""
    _make_active_staff(db, "staff@example.com", "Staff User", "555-5678")

    response = client.get(
        "/api/users/me", headers={"X-Forwarded-User": "staff@example.com"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "staff@example.com"
    assert data["role"] == "staff"
    assert data["is_dj_network"] is False
    assert data["profile"]["name"] == "Staff User"
    assert data["profile"]["phone"] == "555-5678"


def test_inactive_staff_is_unauthorized(client: TestClient, db: Session):
    """Staff member without 'Active' status is treated as unauthorized."""
    staff = Staff(email="inactive@example.com", name="Inactive User", phone="555-0000")
    db.add(staff)
    db.flush()
    db.add(StaffStatus(staff_id=staff.id, status="Inactive"))
    db.commit()

    response = client.get(
        "/api/users/me", headers={"X-Forwarded-User": "inactive@example.com"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "unauthorized"


def test_get_current_user_google_not_in_staff_returns_unauthorized(client: TestClient):
    """Google-authenticated user not in the staff list gets role=unauthorized."""
    response = client.get(
        "/api/users/me", headers={"X-Forwarded-User": "stranger@example.com"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "stranger@example.com"
    assert data["role"] == "unauthorized"
    assert data["is_dj_network"] is False
    assert data["profile"] is None


def test_get_current_user_google_not_in_staff_on_dj_network_returns_dj(client: TestClient):
    """Google-authenticated non-staff user on the DJ network still gets role=dj."""
    response = client.get(
        "/api/users/me",
        headers={
            "X-Forwarded-User": "stranger@example.com",
            "X-Forwarded-For": "192.168.1.5",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "stranger@example.com"
    assert data["role"] == "dj"
    assert data["is_dj_network"] is True
    assert data["profile"] is None


def test_get_current_user_no_auth(client: TestClient):
    """Request with no identity (no X-Forwarded-User, not DJ network) is rejected at auth layer."""
    response = client.get("/api/users/me")

    assert response.status_code == 400
    assert "authentication layer" in response.json()["detail"]


def test_get_current_user_dj_network_unauthenticated(client: TestClient):
    """Test unauthenticated request from DJ studio network returns DJ role."""
    response = client.get("/api/users/me", headers={"X-Forwarded-For": "192.168.1.5"})

    assert response.status_code == 200
    data = response.json()
    assert data["email"] is None
    assert data["role"] == "dj"
    assert data["is_dj_network"] is True
    assert data["profile"] is None


def test_get_current_user_outside_dj_network_unauthenticated(client: TestClient):
    """Request with no Google identity and a non-DJ-network IP is rejected at the auth layer."""
    response = client.get("/api/users/me", headers={"X-Forwarded-For": "10.0.0.5"})

    assert response.status_code == 400
    assert "authentication layer" in response.json()["detail"]


def test_get_current_user_impersonating_dj_network_only(
    client: TestClient, db: Session, monkeypatch
):
    """Staging: DJ-network impersonation with no email simulates unauthenticated DJ access."""
    from app import config
    from app.models.impersonation_session import ImpersonationSession

    monkeypatch.setattr(config.settings, "environment", "staging")

    _make_promotions_staff(db, "promo@example.com", "Promo User", "555-1234")
    db.add(
        ImpersonationSession(
            real_email="promo@example.com",
            impersonated_email=None,
            impersonate_dj_network=True,
        )
    )
    db.commit()

    response = client.get(
        "/api/users/me", headers={"X-Forwarded-User": "promo@example.com"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] is None
    assert data["role"] == "dj"
    assert data["is_dj_network"] is True
    assert data["real_email"] == "promo@example.com"
    assert data["is_impersonating_dj_network"] is True


def test_get_profile_promotions(client: TestClient, db: Session):
    """Test getting promotions staff profile."""
    _make_promotions_staff(db, "promo@example.com", "Promo User", "555-1234")

    response = client.get(
        "/api/users/profile", headers={"X-Forwarded-User": "promo@example.com"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "promo@example.com"
    assert data["name"] == "Promo User"
    assert data["phone"] == "555-1234"


def test_get_profile_promotions_who_is_also_sublist_dj(client: TestClient, db: Session):
    """The /profile endpoint must also report is_sublist_dj for a promotions-role
    staff member who holds Sublist DJ status."""
    staff = _make_promotions_staff(db, "promo-dj@example.com", "Promo DJ User", "555-1234")
    db.add(StaffStatus(staff_id=staff.id, status="Sublist DJ"))
    db.commit()

    response = client.get(
        "/api/users/profile", headers={"X-Forwarded-User": "promo-dj@example.com"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["is_sublist_dj"] is True


def test_get_profile_staff(client: TestClient, db: Session):
    """Test getting staff member profile."""
    _make_active_staff(db, "staff@example.com", "Staff User", "555-5678")

    response = client.get(
        "/api/users/profile", headers={"X-Forwarded-User": "staff@example.com"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "staff@example.com"
    assert data["name"] == "Staff User"
    assert data["phone"] == "555-5678"


def test_get_profile_creates_if_not_exists(client: TestClient, db: Session):
    """Test that getting profile returns existing empty profile for active staff."""
    _make_active_staff(db, "newstaff@example.com", "", "")

    response = client.get(
        "/api/users/profile", headers={"X-Forwarded-User": "newstaff@example.com"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "newstaff@example.com"
    assert data["name"] == ""
    assert data["phone"] == ""


def test_get_profile_dj_forbidden(client: TestClient):
    """Test that DJs cannot get profiles."""
    response = client.get(
        "/api/users/profile", headers={"X-Forwarded-User": "dj@example.com"}
    )

    assert response.status_code == 403
    assert "DJs do not have profiles" in response.json()["detail"]


# --- Airtable sync tests ---


def test_sync_requires_promotions_staff(client: TestClient):
    """Test that sync endpoint requires promotions staff role."""
    response = client.post(
        "/api/users/sync", headers={"X-Forwarded-User": "random@example.com"}
    )
    assert response.status_code == 403


def test_sync_requires_authentication(client: TestClient):
    """Sync endpoint with no identity is rejected at the auth layer."""
    response = client.post("/api/users/sync")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_sync_populates_promotions_from_airtable(client: TestClient, db: Session):
    """Test sync upserts Promotions department users into staff and staff_departments tables."""
    from unittest.mock import patch, AsyncMock

    _make_promotions_staff(db, "admin@example.com", "Admin", "555-0000")

    airtable_records = [
        {
            "Email address": "promouser@example.com",
            "Department": ["Promotions"],
            "Status": ["Active"],
        },
        {
            "Email address": "staffuser@example.com",
            "Department": ["Music", "Operations"],
            "Status": ["Active"],
        },
    ]

    with patch(
        "app.services.user_service.UserService.fetch_airtable_records",
        new_callable=AsyncMock,
        return_value=airtable_records,
    ):
        response = client.post(
            "/api/users/sync", headers={"X-Forwarded-User": "admin@example.com"}
        )

    assert response.status_code == 200
    data = response.json()
    assert "promouser@example.com" in data["promotions_upserted"]
    assert "promouser@example.com" in data["staff_upserted"]
    assert "staffuser@example.com" in data["staff_upserted"]
    assert data["errors"] == []

    # Promotions users have a Promotions department entry
    promo_user = db.query(Staff).filter_by(email="promouser@example.com").first()
    assert promo_user is not None
    assert (
        db.query(StaffDepartment)
        .filter_by(staff_id=promo_user.id, department="Promotions")
        .first()
        is not None
    )
    assert (
        db.query(StaffStatus).filter_by(staff_id=promo_user.id, status="Active").first()
        is not None
    )
    # Non-promotions users are in staff only, not Promotions department
    other_user = db.query(Staff).filter_by(email="staffuser@example.com").first()
    assert other_user is not None
    assert (
        db.query(StaffDepartment)
        .filter_by(staff_id=other_user.id, department="Promotions")
        .first()
        is None
    )


@pytest.mark.asyncio
async def test_sync_paid_staff_gets_promotions_role(client: TestClient, db: Session):
    """Sync: user with 'Paid Staff' + 'Active' statuses gets promotions role after sync."""
    from unittest.mock import patch, AsyncMock

    _make_promotions_staff(db, "admin@example.com", "Admin", "555-0000")

    airtable_records = [
        {
            "Email address": "paidstaff@example.com",
            "Department": ["Music"],
            "Status": ["Paid Staff", "Active"],
        },
    ]

    with patch(
        "app.services.user_service.UserService.fetch_airtable_records",
        new_callable=AsyncMock,
        return_value=airtable_records,
    ):
        client.post("/api/users/sync", headers={"X-Forwarded-User": "admin@example.com"})

    response = client.get(
        "/api/users/me", headers={"X-Forwarded-User": "paidstaff@example.com"}
    )
    assert response.status_code == 200
    assert response.json()["role"] == "promotions"


@pytest.mark.asyncio
async def test_sync_idempotent(client: TestClient, db: Session):
    """Test that running sync twice does not duplicate records."""
    from unittest.mock import patch, AsyncMock

    _make_promotions_staff(db, "admin@example.com", "Admin", "555-0000")

    airtable_records = [
        {
            "Email address": "user@example.com",
            "Department": ["Library"],
            "Status": ["Active"],
        },
    ]

    with patch(
        "app.services.user_service.UserService.fetch_airtable_records",
        new_callable=AsyncMock,
        return_value=airtable_records,
    ):
        client.post("/api/users/sync", headers={"X-Forwarded-User": "admin@example.com"})
        client.post("/api/users/sync", headers={"X-Forwarded-User": "admin@example.com"})

    assert db.query(Staff).filter_by(email="user@example.com").count() == 1
    assert db.query(StaffStatus).filter_by(status="Active").count() >= 1


# --- Notification preferences tests ---


def test_get_notification_preferences_creates_defaults(client: TestClient, db: Session):
    """GET notification-preferences creates and returns defaults when none exist."""
    _make_active_staff(db, "staff@example.com", "Staff User", "555-5678")

    response = client.get(
        "/api/users/notification-preferences",
        headers={"X-Forwarded-User": "staff@example.com"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email_enabled"] is True


def test_get_notification_preferences_returns_existing(client: TestClient, db: Session):
    """GET notification-preferences returns stored value when a row already exists."""
    staff = Staff(email="staff@example.com", name="Staff User", phone="555-5678")
    db.add(staff)
    db.flush()
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.add(NotificationPreferences(staff_id=staff.id, email_enabled=False))
    db.commit()

    response = client.get(
        "/api/users/notification-preferences",
        headers={"X-Forwarded-User": "staff@example.com"},
    )

    assert response.status_code == 200
    assert response.json()["email_enabled"] is False


def test_update_notification_preferences(client: TestClient, db: Session):
    """PUT notification-preferences persists the new value."""
    _make_active_staff(db, "staff@example.com", "Staff User", "555-5678")
    staff = db.query(Staff).filter_by(email="staff@example.com").first()

    response = client.put(
        "/api/users/notification-preferences",
        json={"email_enabled": False},
        headers={"X-Forwarded-User": "staff@example.com"},
    )

    assert response.status_code == 200
    assert response.json()["email_enabled"] is False

    # Verify persisted
    prefs = db.query(NotificationPreferences).filter_by(staff_id=staff.id).first()
    assert prefs is not None
    assert prefs.email_enabled is False


def test_notification_preferences_promotions_staff(client: TestClient, db: Session):
    """Promotions staff can also get and update notification preferences."""
    _make_promotions_staff(db, "promo@example.com", "Promo User", "555-1234")

    response = client.get(
        "/api/users/notification-preferences",
        headers={"X-Forwarded-User": "promo@example.com"},
    )

    assert response.status_code == 200
    assert response.json()["email_enabled"] is True


def test_notification_preferences_requires_authentication(client: TestClient):
    """Notification preferences endpoints with no identity are rejected at the auth layer."""
    assert client.get("/api/users/notification-preferences").status_code == 400
    assert (
        client.put(
            "/api/users/notification-preferences", json={"email_enabled": False}
        ).status_code
        == 400
    )


def test_notification_preferences_dj_forbidden(client: TestClient):
    """DJs (authenticated but no staff record) get 403 for notification preferences."""
    response = client.get(
        "/api/users/notification-preferences",
        headers={"X-Forwarded-User": "dj@example.com"},
    )
    assert response.status_code == 403
