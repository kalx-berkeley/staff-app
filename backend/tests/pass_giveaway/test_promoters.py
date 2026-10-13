"""Tests for who can read promoters."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.promoter import Promoter
from app.models.promoter_contact import PromoterContact
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus


@pytest.fixture
def promoter(db: Session) -> Promoter:
    """A promoter with a contact, whose details only promotions staff may see."""
    promoter = Promoter(name="Big Promoter")
    db.add(promoter)
    db.flush()
    db.add(
        PromoterContact(
            promoter_id=promoter.id, name="Pat", email="pat@example.com", phone="555-0101"
        )
    )
    db.commit()
    return promoter


def _staff(db: Session, email: str, department: str | None = None) -> Staff:
    staff = Staff(email=email, name=email.split("@")[0], phone="555-0000")
    db.add(staff)
    db.flush()
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    if department:
        db.add(StaffDepartment(staff_id=staff.id, department=department))
    db.commit()
    return staff


def test_promotions_staff_can_read_promoters(client: TestClient, db: Session, promoter):
    _staff(db, "promo@example.com", department="Promotions")
    headers = {"X-Forwarded-User": "promo@example.com"}

    listed = client.get("/api/promoters", headers=headers)
    single = client.get(f"/api/promoters/{promoter.id}", headers=headers)

    assert listed.status_code == 200
    assert listed.json()[0]["contacts"][0]["email"] == "pat@example.com"
    assert single.status_code == 200


@pytest.mark.parametrize(
    "headers",
    [
        {"X-Forwarded-User": "staff@example.com"},
        {"X-DJ-Network": "1", "X-Forwarded-For": "192.168.1.100"},
        {"X-Station-Office-Network": "1", "X-Forwarded-For": "192.168.2.50"},
    ],
    ids=["staff", "dj-network-guest", "station-office-guest"],
)
def test_only_promotions_staff_can_read_promoters(
    client: TestClient, db: Session, promoter, headers
):
    _staff(db, "staff@example.com")

    for url in ("/api/promoters", f"/api/promoters/{promoter.id}"):
        response = client.get(url, headers=headers)
        assert response.status_code in (401, 403), url
        assert "pat@example.com" not in response.text


@pytest.mark.parametrize("field", ["show_sourcing_instructions", "pass_call_instructions"])
def test_instructions_can_be_set_and_cleared(
    client: TestClient, db: Session, promoter, field
):
    """Instructions are saved on update and can be cleared again."""
    _staff(db, "promo@example.com", department="Promotions")
    headers = {"X-Forwarded-User": "promo@example.com"}

    set_response = client.put(
        f"/api/promoters/{promoter.id}",
        json={field: "They email a list on the 1st."},
        headers=headers,
    )
    cleared_response = client.put(
        f"/api/promoters/{promoter.id}",
        json={field: None},
        headers=headers,
    )

    assert set_response.status_code == 200
    assert set_response.json()[field] == "They email a list on the 1st."
    assert cleared_response.status_code == 200
    assert cleared_response.json()[field] is None
