"""Tests for venue endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus


@pytest.fixture
def test_promotions_staff(db: Session):
    """Create a test promotions staff member."""
    staff = Staff(email="promotions@test.com", name="Test Promotions", phone="555-0100")
    db.add(staff)
    db.flush()
    db.add(StaffDepartment(staff_id=staff.id, department="Promotions"))
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.commit()
    db.refresh(staff)
    return staff


def test_create_venue(client: TestClient, test_promotions_staff):
    """Test creating a venue."""
    response = client.post(
        "/api/venues",
        json={"name": "The Crocodile", "address": "2505 1st Ave, Seattle, WA 98121"},
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "The Crocodile"
    assert data["address"] == "2505 1st Ave, Seattle, WA 98121"
    assert "id" in data


def test_list_venues(client: TestClient, test_promotions_staff):
    """Test listing venues."""
    # Create some venues
    client.post(
        "/api/venues",
        json={"name": "Venue A", "address": "Address A"},
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    client.post(
        "/api/venues",
        json={"name": "Venue B", "address": "Address B"},
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )

    response = client.get(
        "/api/venues", headers={"X-Forwarded-User": test_promotions_staff.email}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "Venue A"
    assert data[1]["name"] == "Venue B"


def test_get_venue(client: TestClient, test_promotions_staff):
    """Test getting a specific venue."""
    # Create a venue
    create_response = client.post(
        "/api/venues",
        json={"name": "Test Venue", "address": "Test Address"},
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    venue_id = create_response.json()["id"]

    # Get the venue
    response = client.get(
        f"/api/venues/{venue_id}",
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Venue"
    assert data["address"] == "Test Address"


def test_get_nonexistent_venue(client: TestClient):
    """Test getting a venue that doesn't exist."""
    response = client.get(
        "/api/venues/999", headers={"X-Forwarded-User": "anyone@example.com"}
    )
    assert response.status_code == 404


def test_update_venue(client: TestClient, test_promotions_staff):
    """Test updating a venue."""
    # Create a venue
    create_response = client.post(
        "/api/venues",
        json={"name": "Original Name", "address": "Original Address"},
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    venue_id = create_response.json()["id"]

    # Update the venue
    response = client.put(
        f"/api/venues/{venue_id}",
        json={"name": "Updated Name", "address": "Updated Address"},
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["address"] == "Updated Address"


@pytest.mark.parametrize(
    "field",
    [
        "show_sourcing_instructions",
        "pass_call_instructions",
        "default_on_air_description",
        "default_caller_special_instructions",
    ],
)
def test_text_fields_can_be_set_and_cleared(
    client: TestClient, test_promotions_staff, field
):
    """Venue text fields are saved on create and can be cleared on update."""
    headers = {"X-Forwarded-User": test_promotions_staff.email}
    create_response = client.post(
        "/api/venues",
        json={
            "name": "Ivy Room",
            "address": "860 San Pablo Ave, Albany, CA",
            field: "Check the calendar and ask the booker.",
        },
        headers=headers,
    )
    assert create_response.status_code == 201
    venue = create_response.json()
    assert venue[field] == "Check the calendar and ask the booker."

    response = client.put(
        f"/api/venues/{venue['id']}",
        json={field: None},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()[field] is None


def test_win_frequency_days_can_be_cleared(client: TestClient, test_promotions_staff):
    """Sending null for win_frequency_days clears it, as the form does when it's emptied."""
    headers = {"X-Forwarded-User": test_promotions_staff.email}
    create_response = client.post(
        "/api/venues",
        json={"name": "Ivy Room", "address": "860 San Pablo Ave", "win_frequency_days": 30},
        headers=headers,
    )
    assert create_response.status_code == 201
    venue = create_response.json()
    assert venue["win_frequency_days"] == 30

    response = client.put(
        f"/api/venues/{venue['id']}",
        json={"win_frequency_days": None},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["win_frequency_days"] is None


def test_default_wheelchair_accessible_can_be_unknown_or_cleared(
    client: TestClient, test_promotions_staff
):
    """A venue's wheelchair default can be "unknown", and null means no default."""
    headers = {"X-Forwarded-User": test_promotions_staff.email}
    create_response = client.post(
        "/api/venues",
        json={
            "name": "Ivy Room",
            "address": "860 San Pablo Ave",
            "default_wheelchair_accessible": "unknown",
        },
        headers=headers,
    )
    assert create_response.status_code == 201
    venue = create_response.json()
    assert venue["default_wheelchair_accessible"] == "unknown"

    response = client.put(
        f"/api/venues/{venue['id']}",
        json={"default_wheelchair_accessible": None},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["default_wheelchair_accessible"] is None


def test_create_duplicate_venue_name(client: TestClient, test_promotions_staff):
    """Test that creating a venue with duplicate name fails."""
    # Create first venue
    client.post(
        "/api/venues",
        json={"name": "Duplicate", "address": "Address 1"},
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )

    # Try to create second venue with same name
    response = client.post(
        "/api/venues",
        json={"name": "Duplicate", "address": "Address 2"},
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_update_venue_duplicate_name(client: TestClient, test_promotions_staff):
    """Test that updating a venue to a duplicate name fails."""
    # Create two venues
    client.post(
        "/api/venues",
        json={"name": "Venue A", "address": "Address A"},
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    create_response = client.post(
        "/api/venues",
        json={"name": "Venue B", "address": "Address B"},
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    venue_b_id = create_response.json()["id"]

    # Try to update Venue B to have the same name as Venue A
    response = client.put(
        f"/api/venues/{venue_b_id}",
        json={"name": "Venue A"},
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_create_venue_requires_auth(client: TestClient):
    """Test that creating a venue without any identity is rejected at the auth layer."""
    response = client.post(
        "/api/venues", json={"name": "Test Venue", "address": "Test Address"}
    )
    assert response.status_code == 400


def test_create_venue_requires_promotions_staff(client: TestClient, db: Session):
    """Test that creating a venue requires promotions staff role."""
    # Create a non-promotions user (staff member)
    from app.models.staff import Staff
    from app.models.staff_status import StaffStatus

    staff = Staff(email="staff@test.com", name="Test Staff", phone="555-0200")
    db.add(staff)
    db.flush()
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.commit()

    response = client.post(
        "/api/venues",
        json={"name": "Test Venue", "address": "Test Address"},
        headers={"X-Forwarded-User": staff.email},
    )
    assert response.status_code == 403


def test_update_venue_requires_promotions_staff(
    client: TestClient, test_promotions_staff, db: Session
):
    """Test that updating a venue requires promotions staff role."""
    # Create a venue as promotions staff
    create_response = client.post(
        "/api/venues",
        json={"name": "Test Venue", "address": "Test Address"},
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    venue_id = create_response.json()["id"]

    # Create a non-promotions user (staff member)
    from app.models.staff import Staff
    from app.models.staff_status import StaffStatus

    staff = Staff(email="staff@test.com", name="Test Staff", phone="555-0200")
    db.add(staff)
    db.flush()
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.commit()

    # Try to update as staff member
    response = client.put(
        f"/api/venues/{venue_id}",
        json={"name": "Updated Name"},
        headers={"X-Forwarded-User": staff.email},
    )
    assert response.status_code == 403
