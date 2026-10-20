"""Tests for specialty shows' Spinitron shows and retiring."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.specialty_show import SpecialtyShow
from app.models.specialty_show_owner import SpecialtyShowOwner
from app.models.specialty_show_spinitron_show import SpecialtyShowSpinitronShow
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus
from app.pass_giveaway.services.specialty_show_spinitron import specialty_show_ids

PROMO = {"X-Forwarded-User": "promo@example.com"}
SHOWS = {
    301137: {"id": 301137, "title": "Take Five"},
    400: {"id": 400, "title": "Old Take Five"},
}
PLAYLISTS = {23203968: {"id": 23203968, "show_id": 301137}}


@pytest.fixture
def promo(db: Session) -> Staff:
    staff = Staff(email="promo@example.com", name="Promo", phone="")
    db.add(staff)
    db.flush()
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    db.add(StaffDepartment(staff_id=staff.id, department="Promotions"))
    db.commit()
    return staff


@pytest.fixture(autouse=True)
def spinitron():
    with (
        patch(
            "app.common.services.spinitron_service.SpinitronService.fetch_show",
            new_callable=AsyncMock,
            side_effect=lambda show_id: SHOWS.get(show_id),
        ),
        patch(
            "app.common.services.spinitron_service.SpinitronService.fetch_playlist",
            new_callable=AsyncMock,
            side_effect=lambda playlist_id: PLAYLISTS.get(playlist_id),
        ),
    ):
        yield


def _create(
    client, name="Take Five", urls=("https://spinitron.com/KALX/show/301137/Take-Five",)
):
    return client.post(
        "/api/specialty-shows",
        json={"name": name, "spinitron_urls": list(urls)},
        headers=PROMO,
    )


def test_creating_a_show_needs_a_spinitron_link(client: TestClient, promo):
    response = client.post(
        "/api/specialty-shows", json={"name": "Take Five"}, headers=PROMO
    )
    assert response.status_code == 422
    response = _create(client, urls=[""])
    assert response.status_code == 400


@pytest.mark.parametrize(
    "url",
    [
        "https://spinitron.com/KALX/show/301137/Take-Five",
        "https://widgets.spinitron.com/KALX/show/301137/Take-Five",
        "https://widgets.spinitron.com/KALX/pl/23203968/Take-Five",
    ],
)
def test_show_and_playlist_links_resolve_to_the_show(client: TestClient, promo, url):
    response = _create(client, urls=[url])
    assert response.status_code == 201, response.text
    assert response.json()["spinitron_shows"] == [{
        "id": 301137,
        "title": "Take Five",
        "url": "https://spinitron.com/KALX/show/301137/",
    }]


@pytest.mark.parametrize(
    "url,detail",
    [
        ("https://example.com/show/1", "isn't a Spinitron show or playlist link"),
        ("https://spinitron.com/KALX/show/999/", "Spinitron has no show"),
        ("https://spinitron.com/KALX/pl/1/", "Spinitron has no playlist"),
    ],
)
def test_bad_links(client: TestClient, promo, url, detail):
    response = _create(client, urls=[url])
    assert response.status_code == 400
    assert detail in response.json()["detail"]


def test_a_spinitron_show_belongs_to_one_specialty_show(client: TestClient, promo):
    _create(client)
    response = _create(client, name="Copy")
    assert response.status_code == 400
    assert "already belongs to the specialty show 'Take Five'" in response.json()["detail"]


def test_a_deleted_shows_spinitron_show_can_move(client: TestClient, promo, db):
    first = _create(client).json()
    client.delete(f"/api/specialty-shows/{first['id']}", headers=PROMO)
    assert _create(client, name="Take Five, again").status_code == 201


def test_a_show_can_have_several_spinitron_shows(client: TestClient, promo):
    show = _create(client).json()
    response = client.put(
        f"/api/specialty-shows/{show['id']}",
        json={
            "spinitron_urls": [
                "https://spinitron.com/KALX/show/301137/",
                "https://spinitron.com/KALX/show/400/",
                "https://spinitron.com/KALX/pl/23203968/",
            ]
        },
        headers=PROMO,
    )
    assert [s["id"] for s in response.json()["spinitron_shows"]] == [301137, 400]


def test_editing_a_show_without_a_spinitron_show_needs_one(
    client: TestClient, promo, db: Session
):
    show = SpecialtyShow(name="Legacy")
    db.add(show)
    db.commit()
    response = client.put(
        f"/api/specialty-shows/{show.id}", json={"name": "Legacy Show"}, headers=PROMO
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Add the show's Spinitron link"
    response = client.put(
        f"/api/specialty-shows/{show.id}",
        json={
            "name": "Legacy Show",
            "spinitron_urls": ["https://spinitron.com/KALX/show/400/"],
        },
        headers=PROMO,
    )
    assert response.status_code == 200


def test_retiring_a_show(client: TestClient, promo, db: Session):
    show = _create(client).json()
    response = client.post(f"/api/specialty-shows/{show['id']}/retire", headers=PROMO)
    assert response.json()["retired"] is True

    assert client.get("/api/specialty-shows", headers=PROMO).json() == []
    listed = client.get("/api/specialty-shows?include_retired=true", headers=PROMO).json()
    assert [s["retired"] for s in listed] == [True]
    # Its Spinitron show still marks playlists as a specialty show
    assert specialty_show_ids(db) == {301137}

    response = client.post(f"/api/specialty-shows/{show['id']}/unretire", headers=PROMO)
    assert response.json()["retired"] is False
    assert len(client.get("/api/specialty-shows", headers=PROMO).json()) == 1
    events = [
        e.event_type
        for e in db.query(AuditLog).filter(AuditLog.event_type.like("%retired"))
    ]
    assert events == ["specialty_show_retired", "specialty_show_unretired"]


def test_owners_can_retire_and_other_staff_cant(client: TestClient, promo, db: Session):
    show = _create(client).json()
    owner = Staff(email="owner@example.com", name="Owner", phone="")
    other = Staff(email="other@example.com", name="Other", phone="")
    db.add_all([owner, other])
    db.flush()
    db.add_all([
        StaffStatus(staff_id=owner.id, status="Active"),
        StaffStatus(staff_id=other.id, status="Active"),
        SpecialtyShowOwner(specialty_show_id=show["id"], staff_id=owner.id),
    ])
    db.commit()
    response = client.post(
        f"/api/specialty-shows/{show['id']}/retire",
        headers={"X-Forwarded-User": "other@example.com"},
    )
    assert response.status_code == 403
    response = client.post(
        f"/api/specialty-shows/{show['id']}/retire",
        headers={"X-Forwarded-User": "owner@example.com"},
    )
    assert response.status_code == 200


def test_retired_shows_cant_get_passes_or_suggestions(
    client: TestClient, promo, db: Session
):
    from app.pass_giveaway.services.pass_service import PassService

    show = _create(client).json()
    assert "Take Five" in PassService.get_dj_names_for_autocomplete(db)
    client.post(f"/api/specialty-shows/{show['id']}/retire", headers=PROMO)
    assert "Take Five" not in PassService.get_dj_names_for_autocomplete(db)
    assert client.get("/api/specialty-shows/mine", headers=PROMO).json() == []


def test_deleted_shows_spinitron_shows_are_ignored(db: Session):
    show = SpecialtyShow(name="Mistake", deleted=True)
    db.add(show)
    db.flush()
    db.add(SpecialtyShowSpinitronShow(specialty_show_id=show.id, spinitron_show_id=5))
    db.commit()
    assert specialty_show_ids(db) == set()
