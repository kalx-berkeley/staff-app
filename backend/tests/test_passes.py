"""Tests for pass_item endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import date, time, timedelta

from app.models.venue import Venue
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus
from app.models.show import Show
from app.models.pass_model import Pass
from app.services.pass_service import PassService


@pytest.fixture
def venue(db: Session):
    """Create a test venue."""
    venue = Venue(name="Test Venue", address="123 Test St")
    db.add(venue)
    db.commit()
    db.refresh(venue)
    return venue


@pytest.fixture
def promotions_staff(db: Session):
    """Create a test promotions staff member."""
    staff = Staff(email="promotions@test.com", name="Test Promotions", phone="555-0001")
    db.add(staff)
    db.flush()
    db.add(StaffDepartment(staff_id=staff.id, department="Promotions"))
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.commit()
    db.refresh(staff)
    return staff


@pytest.fixture
def staff_member(db: Session):
    """Create a test staff member."""
    staff = Staff(email="staff@test.com", name="Test Staff", phone="555-0002")
    db.add(staff)
    db.flush()
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.commit()
    db.refresh(staff)
    return staff


@pytest.fixture
def show(db: Session, venue, promotions_staff):
    """Create a test show with passes."""
    show = Show(
        event_name="Test Show",
        genre="Rock",
        venue_id=venue.id,
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

    # Create passes manually for this test
    for _ in range(2):
        pass_item = Pass(show_id=show.id, pass_type="pair", status="available")
        db.add(pass_item)
    for _ in range(2):
        pass_item = Pass(show_id=show.id, pass_type="staff", status="available")
        db.add(pass_item)
    db.commit()

    return show


def test_get_show_passes(client, show, promotions_staff):
    """Test getting all passes for a show."""
    response = client.get(
        f"/api/shows/{show.id}/passes",
        headers={"X-Forwarded-User": promotions_staff.email},
    )
    assert response.status_code == 200
    passes = response.json()
    assert len(passes) == 4
    assert sum(1 for t in passes if t["pass_type"] == "pair") == 2
    assert sum(1 for t in passes if t["pass_type"] == "staff") == 2


def test_give_away_pass(client, show, promotions_staff, db):
    """Test giving away a pass pair."""
    # Get a pass pair
    pass_item = (
        db.query(Pass)
        .filter(
            Pass.show_id == show.id,
            Pass.pass_type == "pair",
            Pass.status == "available",
        )
        .first()
    )

    response = client.post(
        f"/api/passes/{pass_item.id}/giveaway",
        json={
            "recipient_name": "John Doe",
            "recipient_phone": "555-1234",
            "given_away_by_dj": "DJ Test",
        },
        headers={"X-Forwarded-User": promotions_staff.email},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "given_away"
    assert data["recipient_name"] == "John Doe"
    assert data["recipient_phone"] == "5551234"
    assert data["given_away_by_dj"] == "DJ Test"
    assert data["given_away_at"] is not None


def test_record_attempt(client, show, promotions_staff, db):
    """Test recording a failed giveaway attempt."""
    response = client.post(
        f"/api/shows/{show.id}/attempt",
        json={"dj_name": "DJ Test"},
        headers={"X-Forwarded-User": promotions_staff.email},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["dj_name"] == "DJ Test"
    assert data["attempted_at"] is not None


def test_claim_staff_pass(client, show, staff_member, db):
    """Test claiming a staff pass."""
    # Get a staff pass
    pass_item = (
        db.query(Pass)
        .filter(
            Pass.show_id == show.id,
            Pass.pass_type == "staff",
            Pass.status == "available",
        )
        .first()
    )

    response = client.post(
        f"/api/passes/{pass_item.id}/claim",
        headers={"X-Forwarded-User": staff_member.email},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "claimed"
    assert data["staff_id"] == staff_member.id
    assert data["claimed_at"] is not None


def test_get_dj_history(client, show, promotions_staff, db):
    """Test getting DJ giveaway history."""
    # Give away a pass
    pass_item = (
        db.query(Pass)
        .filter(
            Pass.show_id == show.id,
            Pass.pass_type == "pair",
            Pass.status == "available",
        )
        .first()
    )

    client.post(
        f"/api/passes/{pass_item.id}/giveaway",
        json={
            "recipient_name": "John Doe",
            "recipient_phone": "555-1234",
            "given_away_by_dj": "DJ Test",
        },
        headers={"X-Forwarded-User": promotions_staff.email},
    )

    # Get history
    response = client.get(
        "/api/passes/my-giveaways?dj_name=DJ Test",
        headers={"X-Forwarded-User": promotions_staff.email},
    )
    assert response.status_code == 200
    passes = response.json()
    assert len(passes) == 1
    assert passes[0]["given_away_by_dj"] == "DJ Test"


def test_get_dj_autocomplete(client, show, promotions_staff, db):
    """Test DJ name autocomplete."""
    # Give away passes with different DJs
    passes = (
        db.query(Pass)
        .filter(
            Pass.show_id == show.id,
            Pass.pass_type == "pair",
            Pass.status == "available",
        )
        .all()
    )

    client.post(
        f"/api/passes/{passes[0].id}/giveaway",
        json={
            "recipient_name": "John Doe",
            "recipient_phone": "555-1234",
            "given_away_by_dj": "DJ Alpha",
        },
        headers={"X-Forwarded-User": promotions_staff.email},
    )

    client.post(
        f"/api/passes/{passes[1].id}/giveaway",
        json={
            "recipient_name": "Jane Doe",
            "recipient_phone": "555-5678",
            "given_away_by_dj": "DJ Beta",
        },
        headers={"X-Forwarded-User": promotions_staff.email},
    )

    # Get autocomplete
    response = client.get(
        "/api/autocomplete/djs", headers={"X-Forwarded-User": promotions_staff.email}
    )
    assert response.status_code == 200
    dj_names = response.json()
    assert "DJ Alpha" in dj_names
    assert "DJ Beta" in dj_names
    assert len(dj_names) == 2


def test_cannot_give_away_closed_show_pass(client, show, promotions_staff, db):
    """Test that passes cannot be given away for closed shows."""
    # Close the show
    show.status = "closed"
    db.commit()

    # Try to give away a pass
    pass_item = (
        db.query(Pass)
        .filter(
            Pass.show_id == show.id,
            Pass.pass_type == "pair",
            Pass.status == "available",
        )
        .first()
    )

    response = client.post(
        f"/api/passes/{pass_item.id}/giveaway",
        json={
            "recipient_name": "John Doe",
            "recipient_phone": "555-1234",
            "given_away_by_dj": "DJ Test",
        },
        headers={"X-Forwarded-User": promotions_staff.email},
    )
    assert response.status_code == 400
    assert "closed" in response.json()["detail"].lower()


def test_cannot_claim_closed_show_pass(client, show, staff_member, db):
    """Test that staff passes cannot be claimed for closed shows."""
    # Close the show
    show.status = "closed"
    db.commit()

    # Try to claim a pass
    pass_item = (
        db.query(Pass)
        .filter(
            Pass.show_id == show.id,
            Pass.pass_type == "staff",
            Pass.status == "available",
        )
        .first()
    )

    response = client.post(
        f"/api/passes/{pass_item.id}/claim",
        headers={"X-Forwarded-User": staff_member.email},
    )
    assert response.status_code == 400
    assert "closed" in response.json()["detail"].lower()


def test_set_preassignment(client, show, promotions_staff, db):
    """Test setting pre-assignment for a pass pair."""
    # Get a pass pair
    pass_item = (
        db.query(Pass)
        .filter(
            Pass.show_id == show.id,
            Pass.pass_type == "pair",
            Pass.status == "available",
        )
        .first()
    )

    response = client.post(
        f"/api/passes/{pass_item.id}/preassign",
        json={"dj_name": "DJ Test", "assignment_date": "2024-12-30"},
        headers={"X-Forwarded-User": promotions_staff.email},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["preassigned_dj"] == "DJ Test"
    assert data["preassigned_date"] == "2024-12-30"
    assert data["status"] == "available"  # Still available


def test_remove_preassignment(client, show, promotions_staff, db):
    """Test removing pre-assignment from a pass pair."""
    # Get a pass pair and set pre-assignment
    pass_item = (
        db.query(Pass)
        .filter(
            Pass.show_id == show.id,
            Pass.pass_type == "pair",
            Pass.status == "available",
        )
        .first()
    )

    # Set pre-assignment
    client.post(
        f"/api/passes/{pass_item.id}/preassign",
        json={"dj_name": "DJ Test", "assignment_date": "2024-12-30"},
        headers={"X-Forwarded-User": promotions_staff.email},
    )

    # Remove pre-assignment
    response = client.delete(
        f"/api/passes/{pass_item.id}/preassign",
        headers={"X-Forwarded-User": promotions_staff.email},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["preassigned_dj"] is None
    assert data["preassigned_date"] is None


def test_cannot_preassign_staff_pass(client, show, promotions_staff, db):
    """Test that staff passes cannot be pre-assigned."""
    # Get a staff pass
    pass_item = (
        db.query(Pass)
        .filter(
            Pass.show_id == show.id,
            Pass.pass_type == "staff",
            Pass.status == "available",
        )
        .first()
    )

    response = client.post(
        f"/api/passes/{pass_item.id}/preassign",
        json={"dj_name": "DJ Test", "assignment_date": "2024-12-30"},
        headers={"X-Forwarded-User": promotions_staff.email},
    )
    assert response.status_code == 400
    assert "pair" in response.json()["detail"].lower()


def test_staff_cannot_preassign(client, show, staff_member, db):
    """Test that staff members cannot pre-assign passes."""
    # Get a pass pair
    pass_item = (
        db.query(Pass)
        .filter(
            Pass.show_id == show.id,
            Pass.pass_type == "pair",
            Pass.status == "available",
        )
        .first()
    )

    response = client.post(
        f"/api/passes/{pass_item.id}/preassign",
        json={"dj_name": "DJ Test", "assignment_date": "2024-12-30"},
        headers={"X-Forwarded-User": staff_member.email},
    )
    assert response.status_code == 403
    assert "promotions" in response.json()["detail"].lower()


# --- Tests for expire_stale_preassignments ---


@pytest.fixture
def published_show_with_passes(db: Session, venue, promotions_staff):
    """Create a published show with two pair passes."""
    show = Show(
        event_name="Expiry Test Show",
        genre="Jazz",
        venue_id=venue.id,
        show_date=date(2025, 1, 1),
        show_time=time(21, 0),
        age_restriction="all_ages",
        wheelchair_accessible=False,
        num_pass_pairs=2,
        status="published",
    )
    db.add(show)
    db.commit()
    db.refresh(show)

    passes = []
    for _ in range(2):
        p = Pass(show_id=show.id, pass_type="pair", status="available")
        db.add(p)
        passes.append(p)
    db.commit()
    for p in passes:
        db.refresh(p)

    return show, passes


def test_expire_stale_preassignment_clears_elapsed_date(db, published_show_with_passes):
    """Passes with a preassigned_date in the past are cleared."""
    _show, passes = published_show_with_passes
    today = date.today()
    yesterday = today - timedelta(days=1)
    passes[0].preassigned_dj = "DJ Stale"
    passes[0].preassigned_date = yesterday
    db.commit()

    result = PassService.expire_stale_preassignments(db, _today=today)

    assert len(result) == 1
    assert result[0].id == passes[0].id
    db.refresh(passes[0])
    assert passes[0].preassigned_dj is None
    assert passes[0].preassigned_date is None
    assert passes[0].status == "available"


def test_expire_stale_preassignment_ignores_future_date(db, published_show_with_passes):
    """Passes with a preassigned_date in the future are not touched."""
    _show, passes = published_show_with_passes
    today = date.today()
    tomorrow = today + timedelta(days=1)
    passes[0].preassigned_dj = "DJ Future"
    passes[0].preassigned_date = tomorrow
    db.commit()

    result = PassService.expire_stale_preassignments(db, _today=today)

    assert len(result) == 0
    db.refresh(passes[0])
    assert passes[0].preassigned_dj == "DJ Future"


def test_expire_stale_preassignment_ignores_today(db, published_show_with_passes):
    """Passes assigned for today are not expired (today has not elapsed)."""
    _show, passes = published_show_with_passes
    today = date.today()
    passes[0].preassigned_dj = "DJ Today"
    passes[0].preassigned_date = today
    db.commit()

    result = PassService.expire_stale_preassignments(db, _today=today)

    assert len(result) == 0
    db.refresh(passes[0])
    assert passes[0].preassigned_dj == "DJ Today"


def test_expire_stale_preassignment_ignores_given_away(db, published_show_with_passes):
    """Given-away passes are not touched even if their preassigned_date is past."""
    _show, passes = published_show_with_passes
    today = date.today()
    yesterday = today - timedelta(days=1)
    passes[0].preassigned_dj = "DJ Done"
    passes[0].preassigned_date = yesterday
    passes[0].status = "given_away"
    db.commit()

    result = PassService.expire_stale_preassignments(db, _today=today)

    assert len(result) == 0
    db.refresh(passes[0])
    assert passes[0].preassigned_dj == "DJ Done"


def test_expire_stale_preassignment_ignores_unassigned(db, published_show_with_passes):
    """Passes with no preassigned_dj are not touched."""
    _show, passes = published_show_with_passes
    # passes have no preassigned_dj by default
    result = PassService.expire_stale_preassignments(db, _today=date.today())
    assert len(result) == 0


def test_expire_stale_preassignment_ignores_closed_show(db, venue, promotions_staff):
    """Passes on closed shows are not cleared."""
    show = Show(
        event_name="Closed Show",
        genre="Rock",
        venue_id=venue.id,
        show_date=date(2025, 1, 1),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible=False,
        num_pass_pairs=1,
        status="closed",
    )
    db.add(show)
    db.commit()
    db.refresh(show)

    today = date.today()
    yesterday = today - timedelta(days=1)
    p = Pass(
        show_id=show.id,
        pass_type="pair",
        status="available",
        preassigned_dj="DJ Old",
        preassigned_date=yesterday,
    )
    db.add(p)
    db.commit()

    result = PassService.expire_stale_preassignments(db, _today=today)

    assert len(result) == 0
    db.refresh(p)
    assert p.preassigned_dj == "DJ Old"


def test_expire_stale_preassignment_ignores_draft_show(db, venue, promotions_staff):
    """Passes on draft shows are not cleared."""
    show = Show(
        event_name="Draft Show",
        genre="Pop",
        venue_id=venue.id,
        show_date=date(2025, 1, 1),
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible=False,
        num_pass_pairs=1,
        status="draft",
    )
    db.add(show)
    db.commit()
    db.refresh(show)

    today = date.today()
    yesterday = today - timedelta(days=1)
    p = Pass(
        show_id=show.id,
        pass_type="pair",
        status="available",
        preassigned_dj="DJ Draft",
        preassigned_date=yesterday,
    )
    db.add(p)
    db.commit()

    result = PassService.expire_stale_preassignments(db, _today=today)

    assert len(result) == 0
    db.refresh(p)
    assert p.preassigned_dj == "DJ Draft"


def test_expire_stale_preassignment_clears_multiple(db, published_show_with_passes):
    """Multiple stale passes on the same show are all cleared."""
    _show, passes = published_show_with_passes
    today = date.today()
    yesterday = today - timedelta(days=1)
    for p in passes:
        p.preassigned_dj = "DJ Multi"
        p.preassigned_date = yesterday
    db.commit()

    result = PassService.expire_stale_preassignments(db, _today=today)

    assert len(result) == 2
    for p in passes:
        db.refresh(p)
        assert p.preassigned_dj is None
        assert p.preassigned_date is None


# --- Tests for search-by-phone and release-winner endpoints ---

DJ_STUDIO_IP = "192.168.1.100"  # within default dj_studio_network 192.168.1.0/24


@pytest.fixture
def given_away_pass(db: Session, show):
    """Create a pass that has been given away to a winner."""
    from app.schemas.pass_schema import GiveawayData

    pass_item = (
        db.query(Pass)
        .filter(
            Pass.show_id == show.id, Pass.pass_type == "pair", Pass.status == "available"
        )
        .first()
    )
    giveaway_data = GiveawayData(
        recipient_name="Jane Winner",
        recipient_phone="555-9999",
        given_away_by_dj="DJ Test",
    )
    return PassService.give_away_pass_pair(db, pass_item.id, giveaway_data)


def test_search_by_phone_no_results(client, show, promotions_staff):
    """Searching for a phone with no matches returns an empty list."""
    response = client.get(
        "/api/passes/search-by-phone",
        params={"phone": "000-0000"},
        headers={"X-Forwarded-User": promotions_staff.email},
    )
    assert response.status_code == 200
    assert response.json() == []


def test_search_by_phone_found(client, show, given_away_pass, promotions_staff):
    """Searching by the winner's phone returns the matching pass."""
    response = client.get(
        "/api/passes/search-by-phone",
        params={"phone": "555-9999"},
        headers={"X-Forwarded-User": promotions_staff.email},
    )
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["id"] == given_away_pass.id
    assert results[0]["recipient_phone"] == "5559999"
    assert results[0]["show_status"] == "published"


def test_search_by_phone_dj_network_access(client, show, given_away_pass):
    """Search endpoint is accessible from the DJ studio network without authentication."""
    response = client.get(
        "/api/passes/search-by-phone",
        params={"phone": "555-9999"},
        headers={"X-Forwarded-For": DJ_STUDIO_IP},
    )
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_search_by_phone_rate_limited(client, show, promotions_staff):
    """Exceeding the per-IP request rate returns 429 with retry_after."""
    from app.main import app
    from app.rate_limiter import create_rate_limit_dependency
    from app.routers.passes import _phone_search_rate_limit

    tight_limit = create_rate_limit_dependency(max_requests=2, window_seconds=60)
    app.dependency_overrides[_phone_search_rate_limit] = tight_limit
    try:
        for _ in range(2):
            r = client.get(
                "/api/passes/search-by-phone",
                params={"phone": "000-0000"},
                headers={"X-Forwarded-User": promotions_staff.email},
            )
            assert r.status_code == 200

        r = client.get(
            "/api/passes/search-by-phone",
            params={"phone": "000-0000"},
            headers={"X-Forwarded-User": promotions_staff.email},
        )
        assert r.status_code == 429
        data = r.json()
        assert "retry_after" in data
        assert isinstance(data["retry_after"], int)
        assert data["retry_after"] > 0
        assert "Retry-After" in r.headers
        assert r.headers["Retry-After"] == str(data["retry_after"])
    finally:
        del app.dependency_overrides[_phone_search_rate_limit]


def test_search_by_phone_rate_limit_per_ip(client, show, promotions_staff):
    """Rate limiting is tracked separately per client IP."""
    from app.main import app
    from app.rate_limiter import create_rate_limit_dependency
    from app.routers.passes import _phone_search_rate_limit

    tight_limit = create_rate_limit_dependency(max_requests=1, window_seconds=60)
    app.dependency_overrides[_phone_search_rate_limit] = tight_limit
    try:
        # First IP hits its limit
        client.get(
            "/api/passes/search-by-phone",
            params={"phone": "000-0000"},
            headers={
                "X-Forwarded-User": promotions_staff.email,
                "X-Forwarded-For": "10.0.0.1",
            },
        )
        r = client.get(
            "/api/passes/search-by-phone",
            params={"phone": "000-0000"},
            headers={
                "X-Forwarded-User": promotions_staff.email,
                "X-Forwarded-For": "10.0.0.1",
            },
        )
        assert r.status_code == 429

        # Different IP still has its own fresh window
        r2 = client.get(
            "/api/passes/search-by-phone",
            params={"phone": "000-0000"},
            headers={
                "X-Forwarded-User": promotions_staff.email,
                "X-Forwarded-For": "10.0.0.2",
            },
        )
        assert r2.status_code == 200
    finally:
        del app.dependency_overrides[_phone_search_rate_limit]


def test_release_winner_success(client, show, given_away_pass, promotions_staff, db):
    """Releasing a winner resets the pass to available and removes the winner record."""
    from app.models.on_air_winner import OnAirWinner

    response = client.post(
        f"/api/passes/{given_away_pass.id}/release-winner",
        json={"reason": "Winner can no longer attend."},
        headers={"X-Forwarded-User": promotions_staff.email},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "available"
    assert data["recipient_name"] is None
    assert data["recipient_phone"] is None
    assert data["given_away_by_dj"] is None

    # Verify OnAirWinner record is gone
    winner = db.query(OnAirWinner).filter(OnAirWinner.pass_id == given_away_pass.id).first()
    assert winner is None


def test_release_winner_from_dj_network_with_identity(client, show, given_away_pass):
    """Unauthenticated DJ network users can release if they supply name and email."""
    response = client.post(
        f"/api/passes/{given_away_pass.id}/release-winner",
        json={
            "reason": "Winner called in and can't make it.",
            "releasing_name": "DJ Bob",
            "releasing_email": "djbob@kalx.example",
        },
        headers={"X-Forwarded-For": DJ_STUDIO_IP},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "available"


def test_release_winner_requires_identity_without_auth(client, show, given_away_pass):
    """Unauthenticated requests must supply releasing_name and releasing_email."""
    response = client.post(
        f"/api/passes/{given_away_pass.id}/release-winner",
        json={"reason": "No identity provided."},
        headers={"X-Forwarded-For": DJ_STUDIO_IP},
    )
    assert response.status_code == 422
    assert "releasing_name" in response.json()["detail"].lower()


def test_release_winner_closed_show(client, show, given_away_pass, promotions_staff, db):
    """Releasing a winner on a closed show returns 400."""
    show.status = "closed"
    db.commit()

    response = client.post(
        f"/api/passes/{given_away_pass.id}/release-winner",
        json={"reason": "Show is closed."},
        headers={"X-Forwarded-User": promotions_staff.email},
    )
    assert response.status_code == 400
    assert "closed" in response.json()["detail"].lower()


def test_release_winner_no_winner(client, show, promotions_staff, db):
    """Releasing a pass that has no winner returns 400."""
    pass_item = (
        db.query(Pass)
        .filter(
            Pass.show_id == show.id, Pass.pass_type == "pair", Pass.status == "available"
        )
        .first()
    )

    response = client.post(
        f"/api/passes/{pass_item.id}/release-winner",
        json={"reason": "No winner here."},
        headers={"X-Forwarded-User": promotions_staff.email},
    )
    assert response.status_code == 400
    assert "winner" in response.json()["detail"].lower()
