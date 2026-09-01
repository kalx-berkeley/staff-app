"""Tests for show API endpoints."""

import pytest
from datetime import date, time
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.venue import Venue
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus


@pytest.fixture
def test_venue(db: Session):
    """Create a test venue."""
    venue = Venue(name="Test Venue", address="123 Test St")
    db.add(venue)
    db.commit()
    db.refresh(venue)
    return venue


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


def test_create_show(client: TestClient, test_venue, test_promotions_staff):
    """Test creating a new show."""
    show_data = {
        "event_name": "Test Concert",
        "genre": ["Rock"],
        "venue_id": test_venue.id,
        "show_date": "2024-12-31",
        "show_time": "20:00:00",
        "caller_special_instructions": "Doors open at 7pm",
        "age_restriction": "21+",
        "wheelchair_accessible": True,
        "num_pass_pairs": 3,
    }

    response = client.post(
        "/api/shows",
        json=show_data,
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["event_name"] == "Test Concert"
    assert data["genre"] == ["rock"]
    assert data["status"] == "draft"
    assert data["venue"]["id"] == test_venue.id
    assert data["promotions_contacts"] == []


def test_create_show_requires_auth(client: TestClient, test_venue):
    """Test that creating a show requires authentication."""
    show_data = {
        "event_name": "Test Concert",
        "genre": "Rock",
        "venue_id": test_venue.id,
        "show_date": "2024-12-31",
        "show_time": "20:00:00",
        "age_restriction": "all_ages",
        "wheelchair_accessible": True,
        "num_pass_pairs": 2,
    }

    response = client.post("/api/shows", json=show_data)
    assert response.status_code == 400


def test_create_show_requires_promotions_staff(client: TestClient, test_venue, db: Session):
    """Test that creating a show requires promotions staff role."""
    show_data = {
        "event_name": "Test Concert",
        "genre": "Rock",
        "venue_id": test_venue.id,
        "show_date": "2024-12-31",
        "show_time": "20:00:00",
        "age_restriction": "all_ages",
        "wheelchair_accessible": True,
        "num_pass_pairs": 2,
    }

    response = client.post(
        "/api/shows",
        json=show_data,
        headers={"X-Forwarded-User": "notpromotions@test.com"},
    )
    assert response.status_code == 403


def test_list_shows(client: TestClient, test_venue, test_promotions_staff, db: Session):
    """Test listing all shows."""
    # Create a show directly in database
    from app.models.show import Show

    show = Show(
        event_name="Test Show",
        genre=["Jazz"],
        venue_id=test_venue.id,
        show_date=date(2024, 12, 31),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible=True,
        num_pass_pairs=2,
        status="draft",
    )
    db.add(show)
    db.commit()

    response = client.get(
        "/api/shows", headers={"X-Forwarded-User": test_promotions_staff.email}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["event_name"] == "Test Show"


def test_get_show(client: TestClient, test_venue, test_promotions_staff, db: Session):
    """Test getting a specific show."""
    from app.models.show import Show

    show = Show(
        event_name="Test Show",
        genre=["Jazz"],
        venue_id=test_venue.id,
        show_date=date(2024, 12, 31),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible=True,
        num_pass_pairs=2,
        status="draft",
    )
    db.add(show)
    db.commit()
    db.refresh(show)

    response = client.get(
        f"/api/shows/{show.id}",
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["event_name"] == "Test Show"
    assert data["venue"]["name"] == test_venue.name


def test_update_show(client: TestClient, test_venue, test_promotions_staff, db: Session):
    """Test updating a show."""
    from app.models.show import Show

    show = Show(
        event_name="Test Show",
        genre=["Jazz"],
        venue_id=test_venue.id,
        show_date=date(2024, 12, 31),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible=True,
        num_pass_pairs=2,
        status="draft",
    )
    db.add(show)
    db.commit()
    db.refresh(show)

    update_data = {"event_name": "Updated Show"}
    response = client.put(
        f"/api/shows/{show.id}",
        json=update_data,
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["event_name"] == "Updated Show"


def test_publish_show(client: TestClient, test_venue, test_promotions_staff, db: Session):
    """Test publishing a show."""
    from app.models.show import Show

    show = Show(
        event_name="Test Show",
        genre=["Jazz"],
        venue_id=test_venue.id,
        show_date=date(2024, 12, 31),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible=True,
        num_pass_pairs=2,
        status="draft",
    )
    db.add(show)
    db.commit()
    db.refresh(show)

    response = client.post(
        f"/api/shows/{show.id}/publish",
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "published"


def test_close_show(client: TestClient, test_venue, test_promotions_staff, db: Session):
    """Test closing a show."""
    from app.models.show import Show

    show = Show(
        event_name="Test Show",
        genre=["Jazz"],
        venue_id=test_venue.id,
        show_date=date(2024, 12, 31),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible=True,
        num_pass_pairs=2,
        status="published",
    )
    db.add(show)
    db.commit()
    db.refresh(show)

    response = client.post(
        f"/api/shows/{show.id}/close",
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "closed"


def test_invalid_status_transition(
    client: TestClient, test_venue, test_promotions_staff, db: Session
):
    """Test that invalid status transitions are rejected."""
    from app.models.show import Show

    show = Show(
        event_name="Test Show",
        genre=["Jazz"],
        venue_id=test_venue.id,
        show_date=date(2024, 12, 31),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible=True,
        num_pass_pairs=2,
        status="draft",
    )
    db.add(show)
    db.commit()
    db.refresh(show)

    # Try to close a draft show (should fail)
    response = client.post(
        f"/api/shows/{show.id}/close",
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )

    assert response.status_code == 400
    assert "Cannot close show" in response.json()["detail"]


def test_pass_pair_validation(client: TestClient, test_venue, test_promotions_staff):
    """Test that pass pair count is validated."""
    # Test with 0 pairs (should fail)
    show_data = {
        "event_name": "Test Concert",
        "genre": ["Rock"],
        "venue_id": test_venue.id,
        "show_date": "2024-12-31",
        "show_time": "20:00:00",
        "age_restriction": "all_ages",
        "wheelchair_accessible": True,
        "num_pass_pairs": 0,
    }

    response = client.post(
        "/api/shows",
        json=show_data,
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    assert response.status_code == 422

    # Test with 6 pairs (should fail)
    show_data["num_pass_pairs"] = 6
    response = client.post(
        "/api/shows",
        json=show_data,
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    assert response.status_code == 422


def test_role_based_show_visibility(
    client: TestClient, test_venue, test_promotions_staff, db: Session
):
    """Test that shows are filtered based on user role."""
    from app.models.show import Show
    from app.models.staff import Staff
    from app.models.staff_status import StaffStatus

    # Create a staff member
    staff = Staff(email="staff@test.com", name="Test Staff", phone="555-0200")
    db.add(staff)
    db.flush()
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.commit()

    # Create draft, published, and closed shows
    draft_show = Show(
        event_name="Draft Show",
        genre=["Rock"],
        venue_id=test_venue.id,
        show_date=date(2024, 12, 31),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible=True,
        num_pass_pairs=2,
        status="draft",
    )
    published_show = Show(
        event_name="Published Show",
        genre=["Jazz"],
        venue_id=test_venue.id,
        show_date=date(2024, 12, 30),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible=True,
        num_pass_pairs=2,
        status="published",
    )
    closed_show = Show(
        event_name="Closed Show",
        genre=["Blues"],
        venue_id=test_venue.id,
        show_date=date(2024, 12, 29),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible=True,
        num_pass_pairs=2,
        status="closed",
    )
    db.add_all([draft_show, published_show, closed_show])
    db.commit()

    # Promotions staff should see all shows
    response = client.get(
        "/api/shows", headers={"X-Forwarded-User": test_promotions_staff.email}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    event_names = [show["event_name"] for show in data]
    assert "Draft Show" in event_names
    assert "Published Show" in event_names
    assert "Closed Show" in event_names

    # Staff member should only see published and closed shows
    response = client.get("/api/shows", headers={"X-Forwarded-User": staff.email})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    event_names = [show["event_name"] for show in data]
    assert "Draft Show" not in event_names
    assert "Published Show" in event_names
    assert "Closed Show" in event_names


def test_closed_show_prevents_pass_operations(
    client: TestClient, test_venue, test_promotions_staff, db: Session
):
    """Test that closed shows prevent pass_item operations but allow viewing."""
    from app.models.show import Show
    from app.models.pass_model import Pass

    # Create a closed show with passes
    show = Show(
        event_name="Closed Show",
        genre=["Rock"],
        venue_id=test_venue.id,
        show_date=date(2024, 12, 31),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible=True,
        num_pass_pairs=2,
        status="closed",
    )
    db.add(show)
    db.commit()
    db.refresh(show)

    # Create a pass pair
    pass_item = Pass(show_id=show.id, pass_type="pair", status="available")
    db.add(pass_item)
    db.commit()
    db.refresh(pass_item)

    # Viewing the show should still work
    response = client.get(
        f"/api/shows/{show.id}",
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "closed"

    # Attempting to give away a pass should fail (use promotions staff for DJ access)
    giveaway_data = {
        "recipient_name": "John Doe",
        "recipient_phone": "555-1234",
        "given_away_by_dj": "DJ Test",
    }
    response = client.post(
        f"/api/passes/{pass_item.id}/giveaway",
        json=giveaway_data,
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    assert response.status_code == 400
    assert "closed" in response.json()["detail"].lower()


def test_search_shows_freetext(
    client: TestClient, test_venue, test_promotions_staff, db: Session
):
    """Test freetext search across event name, genre, venue name, and special instructions."""
    from app.models.show import Show

    # Create shows with different searchable content
    show1 = Show(
        event_name="Rock Concert with The Beatles",
        genre=["Rock"],
        venue_id=test_venue.id,
        show_date=date(2024, 12, 31),
        show_time=time(20, 0),
        caller_special_instructions="VIP entrance available",
        age_restriction="all_ages",
        wheelchair_accessible=True,
        num_pass_pairs=2,
        status="published",
    )
    show2 = Show(
        event_name="Jazz Night",
        genre=["Jazz"],
        venue_id=test_venue.id,
        show_date=date(2024, 12, 30),
        show_time=time(20, 0),
        caller_special_instructions="Doors open early",
        age_restriction="all_ages",
        wheelchair_accessible=True,
        num_pass_pairs=2,
        status="published",
    )
    db.add_all([show1, show2])
    db.commit()

    # Search by event name
    response = client.get(
        "/api/shows/search?freetext=Beatles",
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["event_name"] == "Rock Concert with The Beatles"

    # Search by genre
    response = client.get(
        "/api/shows/search?freetext=Jazz",
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["event_name"] == "Jazz Night"

    # Search by venue name
    response = client.get(
        f"/api/shows/search?freetext={test_venue.name}",
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    # Search by special instructions
    response = client.get(
        "/api/shows/search?freetext=VIP",
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["event_name"] == "Rock Concert with The Beatles"


def test_search_shows_filters(
    client: TestClient, test_venue, test_promotions_staff, db: Session
):
    """Test filtering by venue, artist, and genre."""
    from app.models.show import Show

    # Create another venue
    venue2 = Venue(name="Another Venue", address="456 Other St")
    db.add(venue2)
    db.commit()
    db.refresh(venue2)

    # Create shows at different venues with different genres
    show1 = Show(
        event_name="The Rolling Stones Live",
        genre=["Rock"],
        venue_id=test_venue.id,
        show_date=date(2024, 12, 31),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible=True,
        num_pass_pairs=2,
        status="published",
    )
    show2 = Show(
        event_name="Jazz Quartet",
        genre=["Jazz"],
        venue_id=venue2.id,
        show_date=date(2024, 12, 30),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible=True,
        num_pass_pairs=2,
        status="published",
    )
    show3 = Show(
        event_name="Blues Brothers Tribute",
        genre=["Blues"],
        venue_id=test_venue.id,
        show_date=date(2024, 12, 29),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible=True,
        num_pass_pairs=2,
        status="published",
    )
    db.add_all([show1, show2, show3])
    db.commit()

    # Filter by venue
    response = client.get(
        f"/api/shows/search?venue_id={test_venue.id}",
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    event_names = [show["event_name"] for show in data]
    assert "The Rolling Stones Live" in event_names
    assert "Blues Brothers Tribute" in event_names
    assert "Jazz Quartet" not in event_names

    # Filter by artist (searches in event name and genre)
    response = client.get(
        "/api/shows/search?artist=Rolling",
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["event_name"] == "The Rolling Stones Live"

    # Filter by genre
    response = client.get(
        "/api/shows/search?genre=Jazz",
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["event_name"] == "Jazz Quartet"


def test_search_shows_role_based_visibility(
    client: TestClient, test_venue, test_promotions_staff, db: Session
):
    """Test that search respects role-based visibility."""
    from app.models.show import Show
    from app.models.staff import Staff
    from app.models.staff_status import StaffStatus

    # Create a staff member
    staff = Staff(email="staff@test.com", name="Test Staff", phone="555-0200")
    db.add(staff)
    db.flush()
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.commit()

    # Create draft and published shows
    draft_show = Show(
        event_name="Draft Rock Show",
        genre=["Rock"],
        venue_id=test_venue.id,
        show_date=date(2024, 12, 31),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible=True,
        num_pass_pairs=2,
        status="draft",
    )
    published_show = Show(
        event_name="Published Rock Show",
        genre=["Rock"],
        venue_id=test_venue.id,
        show_date=date(2024, 12, 30),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible=True,
        num_pass_pairs=2,
        status="published",
    )
    db.add_all([draft_show, published_show])
    db.commit()

    # Promotions staff should see both shows when searching for "Rock"
    response = client.get(
        "/api/shows/search?freetext=Rock",
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    # Staff member should only see published show when searching for "Rock"
    response = client.get(
        "/api/shows/search?freetext=Rock", headers={"X-Forwarded-User": staff.email}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["event_name"] == "Published Rock Show"


def test_show_detail_completeness(
    client: TestClient, test_venue, test_promotions_staff, db: Session
):
    """Test that show details include all pass_item information with recipients, failed attempts, and DJ names."""
    from app.models.show import Show
    from app.models.pass_model import Pass
    from app.models.on_air_winner import OnAirWinner
    from app.models.show_attempt import ShowAttempt
    from app.models.staff import Staff
    from app.models.staff_status import StaffStatus
    from datetime import datetime

    # Create a staff member
    staff = Staff(email="staff@test.com", name="Jane Smith", phone="555-9999")
    db.add(staff)
    db.flush()
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.commit()
    db.refresh(staff)

    # Create a show
    show = Show(
        event_name="Complete Show Test",
        genre=["Rock"],
        venue_id=test_venue.id,
        show_date=date(2024, 12, 31),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible=True,
        num_pass_pairs=2,
        status="published",
    )
    db.add(show)
    db.commit()
    db.refresh(show)

    # Create pass pair that was given away
    pass_given_away = Pass(
        show_id=show.id,
        pass_type="pair",
        status="given_away",
        given_away_by_dj="DJ Cool",
        given_away_at=datetime(2024, 12, 25, 10, 30),
    )

    # Create available pass pair
    pass_available_pair = Pass(show_id=show.id, pass_type="pair", status="available")

    # Create staff pass that was claimed
    pass_claimed = Pass(
        show_id=show.id,
        pass_type="staff",
        status="claimed",
        staff_id=staff.id,
        claimed_at=datetime(2024, 12, 23, 9, 0),
    )

    # Create available staff pass
    pass_available = Pass(show_id=show.id, pass_type="staff", status="available")

    db.add_all([pass_given_away, pass_available_pair, pass_claimed, pass_available])
    db.commit()
    db.refresh(pass_given_away)

    # Create the OnAirWinner record for the given-away pass
    winner = OnAirWinner(
        pass_id=pass_given_away.id,
        venue_id=test_venue.id,
        show_id=show.id,
        recipient_name="John Doe",
        recipient_phone="555-1234",
        given_away_by_dj="DJ Cool",
    )
    db.add(winner)

    # Create a failed attempt record
    attempt = ShowAttempt(
        show_id=show.id,
        dj_name="DJ Retry",
        attempted_at=datetime(2024, 12, 24, 15, 45),
    )
    db.add(attempt)
    db.commit()

    # Get show details
    response = client.get(
        f"/api/shows/{show.id}",
        headers={"X-Forwarded-User": test_promotions_staff.email},
    )
    assert response.status_code == 200
    data = response.json()

    # Verify show has passes array
    assert "passes" in data
    assert len(data["passes"]) == 4

    # Find each pass_item in the response
    passes_by_id = {t["id"]: t for t in data["passes"]}

    # Verify given away pass_item includes recipient and DJ info
    given_away = passes_by_id[pass_given_away.id]
    assert given_away["pass_type"] == "pair"
    assert given_away["status"] == "given_away"
    assert given_away["recipient_name"] == "John Doe"
    assert given_away["recipient_phone"] == "555-1234"
    assert given_away["given_away_by_dj"] == "DJ Cool"
    assert given_away["given_away_at"] is not None

    # Verify claimed staff pass includes staff member info
    claimed = passes_by_id[pass_claimed.id]
    assert claimed["pass_type"] == "staff"
    assert claimed["status"] == "claimed"
    assert claimed["staff_id"] == staff.id
    assert claimed["staff_name"] == "Jane Smith"
    assert claimed["staff_phone"] == "555-9999"
    assert claimed["claimed_at"] is not None

    # Verify available staff pass
    available = passes_by_id[pass_available.id]
    assert available["pass_type"] == "staff"
    assert available["status"] == "available"
    assert available["staff_id"] is None
    assert available["staff_name"] is None
    assert available["staff_phone"] is None

    # Verify failed attempts are in show.attempts
    assert "attempts" in data
    assert len(data["attempts"]) == 1
    assert data["attempts"][0]["dj_name"] == "DJ Retry"
    assert data["attempts"][0]["attempted_at"] is not None
