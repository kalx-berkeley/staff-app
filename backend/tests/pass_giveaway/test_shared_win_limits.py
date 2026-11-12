"""Tests for venues sharing a parent venue's win frequency limit."""

from datetime import date, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.on_air_winner import OnAirWinner
from app.models.pass_model import Pass
from app.models.show import Show
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus
from app.models.venue import Venue

DJ_STUDIO = {"X-Forwarded-For": "192.168.1.100"}  # in the default dj_studio_network


@pytest.fixture
def promo(db: Session) -> dict:
    staff = Staff(email="promo@shared.test", name="Promo", phone="555-0100")
    db.add(staff)
    db.flush()
    db.add(StaffDepartment(staff_id=staff.id, department="Promotions"))
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.commit()
    return {"X-Forwarded-User": staff.email}


def _venue(db: Session, name: str, days=None, parent: Venue | None = None) -> Venue:
    venue = Venue(
        name=name,
        address=f"1 {name} St",
        win_frequency_days=days,
        parent_venue_id=parent.id if parent else None,
    )
    db.add(venue)
    db.commit()
    db.refresh(venue)
    return venue


@pytest.fixture
def elmwood(db: Session) -> Venue:
    return _venue(db, "Elmwood", days=30)


@pytest.fixture
def cerrito(db: Session, elmwood) -> Venue:
    return _venue(db, "Cerrito", parent=elmwood)


def _show(db: Session, venue: Venue, show_date: date, name: str = "Show") -> Show:
    show = Show(
        event_name=name,
        venue_id=venue.id,
        show_date=show_date,
        show_time=time(20, 0),
        age_restriction="all_ages",
        wheelchair_accessible="yes",
        num_pass_pairs=1,
        status="published",
    )
    db.add(show)
    db.flush()
    db.add(Pass(show_id=show.id, pass_type="pair", status="available"))
    db.commit()
    db.refresh(show)
    return show


def _win(db: Session, show: Show, phone: str = "5105550100") -> None:
    p = Pass(
        show_id=show.id, pass_type="pair", status="given_away", given_away_by_dj="DJ X"
    )
    db.add(p)
    db.flush()
    db.add(
        OnAirWinner(
            pass_id=p.id,
            venue_id=show.venue_id,
            show_id=show.id,
            recipient_name="Jane Doe",
            recipient_phone=phone,
            given_away_by_dj="DJ X",
        )
    )
    db.commit()


# ---------------------------------------------------------------------------
# Setting the parent


def test_create_child_venue(client: TestClient, promo, elmwood):
    response = client.post(
        "/api/venues",
        json={"name": "Cerrito", "address": "1 Cerrito St", "parent_venue_id": elmwood.id},
        headers=promo,
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["parent_venue_id"] == elmwood.id
    assert data["parent_venue_name"] == "Elmwood"
    assert data["win_frequency_days"] is None
    assert data["effective_win_frequency_days"] == 30
    assert data["win_frequency_shared_with"] == ["Elmwood"]

    parent = client.get(f"/api/venues/{elmwood.id}", headers=promo).json()
    assert parent["children"] == [{"id": data["id"], "name": "Cerrito"}]
    assert parent["win_frequency_shared_with"] == ["Cerrito"]


def test_choosing_a_parent_clears_own_limit(client: TestClient, db, promo, elmwood):
    other = _venue(db, "Cerrito", days=20)
    response = client.put(
        f"/api/venues/{other.id}", json={"parent_venue_id": elmwood.id}, headers=promo
    )
    assert response.status_code == 200, response.text
    assert response.json()["win_frequency_days"] is None
    assert response.json()["effective_win_frequency_days"] == 30

    row = db.query(AuditLog).filter(AuditLog.event_type == "venue_updated").one()
    changed = row.details["changed_fields"]
    assert changed["parent_venue_id"] == {"before": None, "after": elmwood.id}
    assert changed["win_frequency_days"] == {"before": 20, "after": None}


def test_unlinking_keeps_no_limit(client: TestClient, promo, cerrito):
    response = client.put(
        f"/api/venues/{cerrito.id}", json={"parent_venue_id": None}, headers=promo
    )
    assert response.status_code == 200
    assert response.json()["parent_venue_id"] is None
    assert response.json()["effective_win_frequency_days"] is None


@pytest.mark.parametrize(
    "body",
    [
        {"win_frequency_days": 10},
        {"parent_venue_id": "ELMWOOD", "win_frequency_days": 10},
    ],
)
def test_child_cannot_have_own_limit(client: TestClient, promo, elmwood, cerrito, body):
    body = {k: elmwood.id if v == "ELMWOOD" else v for k, v in body.items()}
    response = client.put(f"/api/venues/{cerrito.id}", json=body, headers=promo)
    assert response.status_code == 400
    assert "can't have its own limit" in response.json()["detail"]


def test_parent_cannot_be_itself(client: TestClient, promo, elmwood):
    response = client.put(
        f"/api/venues/{elmwood.id}",
        json={"parent_venue_id": elmwood.id, "win_frequency_days": None},
        headers=promo,
    )
    assert response.status_code == 400


def test_parent_cannot_be_a_child(client: TestClient, db, promo, cerrito):
    third = _venue(db, "Albany")
    response = client.put(
        f"/api/venues/{third.id}", json={"parent_venue_id": cerrito.id}, headers=promo
    )
    assert response.status_code == 400
    assert "Choose Elmwood instead" in response.json()["detail"]


def test_venue_with_children_cannot_become_a_child(
    client: TestClient, db, promo, elmwood, cerrito
):
    other = _venue(db, "Albany")
    response = client.put(
        f"/api/venues/{elmwood.id}",
        json={"parent_venue_id": other.id, "win_frequency_days": None},
        headers=promo,
    )
    assert response.status_code == 400
    assert "Cerrito" in response.json()["detail"]


def test_parent_must_be_live(client: TestClient, db, promo):
    gone = _venue(db, "Gone", days=30)
    gone.deleted = True
    db.commit()
    response = client.post(
        "/api/venues",
        json={"name": "New", "address": "1 New St", "parent_venue_id": gone.id},
        headers=promo,
    )
    assert response.status_code == 400


def test_parent_without_limit_means_no_limit(client: TestClient, db, promo):
    parent = _venue(db, "Elmwood")
    child = _venue(db, "Cerrito", parent=parent)
    data = client.get(f"/api/venues/{child.id}", headers=promo).json()
    assert data["effective_win_frequency_days"] is None
    assert data["win_frequency_shared_with"] == []


# ---------------------------------------------------------------------------
# Deleting


def test_cannot_delete_parent_with_children(client: TestClient, promo, elmwood, cerrito):
    response = client.delete(f"/api/venues/{elmwood.id}", headers=promo)
    assert response.status_code == 409
    assert "Cerrito" in response.json()["detail"]


def test_deleting_child_unlinks_it(client: TestClient, db, promo, elmwood, cerrito):
    response = client.delete(f"/api/venues/{cerrito.id}", headers=promo)
    assert response.status_code == 204
    db.expire_all()
    assert db.get(Venue, cerrito.id).parent_venue_id is None

    row = db.query(AuditLog).filter(AuditLog.event_type == "venue_deleted").one()
    assert row.details["unlinked_from_parent_venue_id"] == elmwood.id
    assert row.details["unlinked_from_parent_venue"] == "Elmwood"

    # The parent can now be deleted, and the restored child has no parent
    assert client.delete(f"/api/venues/{elmwood.id}", headers=promo).status_code == 204
    restored = client.post(f"/api/venues/{cerrito.id}/undelete", headers=promo).json()
    assert restored["parent_venue_id"] is None
    assert restored["effective_win_frequency_days"] is None


# ---------------------------------------------------------------------------
# The check


def test_check_winner_counts_wins_at_parent(client: TestClient, db, elmwood, cerrito):
    _win(db, _show(db, elmwood, date(2026, 6, 1), name="Elmwood Show"))
    current = _show(db, cerrito, date(2026, 6, 20))

    response = client.get(
        f"/api/venues/{cerrito.id}/check-winner",
        params={"phone": "510-555-0100", "show_id": current.id},
        headers=DJ_STUDIO,
    )
    data = response.json()
    assert data["eligible"] is False
    assert data["last_win_show"] == "Elmwood Show"
    assert data["last_win_venue"] == "Elmwood"
    assert data["required_days"] == 30
    assert data["days_since"] == 19

    row = db.query(AuditLog).filter(AuditLog.event_type == "winner_frequency_warning").one()
    assert row.entity_id == cerrito.id
    assert row.details["last_win_venue_id"] == elmwood.id
    assert row.details["last_win_venue"] == "Elmwood"


def test_check_winner_counts_wins_at_sister_child(client: TestClient, db, elmwood, cerrito):
    albany = _venue(db, "Albany", parent=elmwood)
    _win(db, _show(db, albany, date(2026, 6, 1)))
    current = _show(db, cerrito, date(2026, 6, 20))
    response = client.get(
        f"/api/venues/{cerrito.id}/check-winner",
        params={"phone": "5105550100", "show_id": current.id},
        headers=DJ_STUDIO,
    )
    assert response.json()["eligible"] is False
    assert response.json()["last_win_venue"] == "Albany"


def test_check_winner_ignores_unrelated_venue(client: TestClient, db, elmwood):
    other = _venue(db, "Ivy Room", days=30)
    _win(db, _show(db, other, date(2026, 6, 1)))
    current = _show(db, elmwood, date(2026, 6, 20))
    response = client.get(
        f"/api/venues/{elmwood.id}/check-winner",
        params={"phone": "5105550100", "show_id": current.id},
        headers=DJ_STUDIO,
    )
    assert response.json() == {"eligible": True, "reason": None}


def test_check_winner_outside_limit(client: TestClient, db, elmwood, cerrito):
    _win(db, _show(db, cerrito, date(2026, 6, 1)))
    current = _show(db, elmwood, date(2026, 7, 1))
    response = client.get(
        f"/api/venues/{elmwood.id}/check-winner",
        params={"phone": "5105550100", "show_id": current.id},
        headers=DJ_STUDIO,
    )
    assert response.json()["eligible"] is True


def test_giveaway_override_records_last_win_venue(client: TestClient, db, elmwood, cerrito):
    _win(db, _show(db, elmwood, date(2026, 6, 1)))
    current = _show(db, cerrito, date(2026, 6, 10))
    pair = db.query(Pass).filter(Pass.show_id == current.id).one()
    response = client.post(
        f"/api/passes/{pair.id}/giveaway",
        json={
            "recipient_name": "Jane Doe",
            "recipient_phone": "510-555-0100",
            "given_away_by_dj": "DJ Test",
        },
        headers=DJ_STUDIO,
    )
    assert response.status_code == 200, response.text
    row = db.query(AuditLog).filter(AuditLog.event_type == "venue_frequency_override").one()
    assert row.details["venue_id"] == cerrito.id
    assert row.details["last_win_venue_id"] == elmwood.id
    assert row.details["required_days"] == 30


def test_show_payload_has_effective_limit(client: TestClient, db, promo, elmwood, cerrito):
    show = _show(db, cerrito, date(2026, 6, 10))
    venue = client.get(f"/api/shows/{show.id}", headers=DJ_STUDIO).json()["venue"]
    assert venue["win_frequency_days"] == 30
    assert venue["win_frequency_shared_with"] == ["Elmwood"]
