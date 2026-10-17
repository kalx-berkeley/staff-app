"""Tests for Short Links: the site-admin API and the /go/<slug> redirects."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.common.areas import SHORT_LINKS_AREA
from app.models.audit_log import AuditLog
from app.models.short_link import ShortLink
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus

ADMIN = "admin@example.com"
PROMOTIONS = "promotions@example.com"
STAFF = "staff@example.com"
INACTIVE = "inactive@example.com"


def _make_staff(
    db: Session, email: str, *, statuses=("Active",), department: str | None = None
) -> Staff:
    staff = Staff(email=email, name=email.split("@")[0], phone="")
    db.add(staff)
    db.flush()
    for s in statuses:
        db.add(StaffStatus(staff_id=staff.id, status=s))
    if department:
        db.add(StaffDepartment(staff_id=staff.id, department=department))
    db.commit()
    return staff


@pytest.fixture
def people(db: Session):
    _make_staff(db, ADMIN, statuses=("Active", "Paid Staff"))
    _make_staff(db, PROMOTIONS, department="Promotions")
    _make_staff(db, STAFF)
    _make_staff(db, INACTIVE, statuses=())


def _as(email: str) -> dict:
    return {"X-Forwarded-User": email}


def _create(client: TestClient, **body) -> dict:
    body = {"slug": "Fundraiser", "target_url": "https://example.com/give", **body}
    response = client.post("/api/short-links", json=body, headers=_as(ADMIN))
    assert response.status_code == 201, response.text
    return response.json()


def _audit(db: Session, event_type: str) -> AuditLog:
    return db.query(AuditLog).filter(AuditLog.event_type == event_type).one()


# --- Admin API ---


def test_create_lowercases_slug_and_logs(client: TestClient, db: Session, people):
    link = _create(client, note="  Fall drive  ")

    assert link["slug"] == "fundraiser"
    assert link["note"] == "Fall drive"
    assert link["created_by_email"] == ADMIN
    entry = _audit(db, "short_link_created")
    assert entry.area == SHORT_LINKS_AREA
    assert entry.actor_email == ADMIN
    assert entry.details == {
        "slug": "fundraiser",
        "target_url": "https://example.com/give",
        "note": "Fall drive",
    }


def test_list_is_sorted_by_slug(client: TestClient, people):
    _create(client, slug="zebra")
    _create(client, slug="apple")

    response = client.get("/api/short-links", headers=_as(ADMIN))

    assert [link["slug"] for link in response.json()] == ["apple", "zebra"]


@pytest.mark.parametrize(
    "slug", ["", "-start", "end-", "has space", "under_score", "dot.ted", "a" * 65, "é"]
)
def test_invalid_slugs_are_rejected(client: TestClient, people, slug):
    response = client.post(
        "/api/short-links",
        json={"slug": slug, "target_url": "https://example.com"},
        headers=_as(ADMIN),
    )

    assert response.status_code == 400
    assert "slug" in response.json()["detail"]


@pytest.mark.parametrize("slug", ["a", "0", "a-b", "a" * 64, "Mixed-Case-9"])
def test_valid_slugs_are_accepted(client: TestClient, people, slug):
    assert _create(client, slug=slug)["slug"] == slug.lower()


@pytest.mark.parametrize(
    "target",
    [
        "javascript:alert(1)",
        "data:text/html,hi",
        "ftp://example.com/file",
        "//evil.example.com",
        "/workforms/",
        "example.com",
        "https://",
        "https://example.com/has space",
        "https://example.com/" + "a" * 2048,
        # This site's own short links would loop
        "https://testserver/go/other",
        "http://TESTSERVER/GO/other",
        "https://testserver/go",
    ],
)
def test_invalid_targets_are_rejected(client: TestClient, people, target):
    response = client.post(
        "/api/short-links",
        json={"slug": "x", "target_url": target},
        headers=_as(ADMIN),
    )

    assert response.status_code == 400


@pytest.mark.parametrize(
    "target",
    [
        "http://example.com",
        "https://testserver/workforms/",
        "https://other.example.com/go/elsewhere",
    ],
)
def test_valid_targets_are_accepted(client: TestClient, people, target):
    assert _create(client, target_url=target)["target_url"] == target


def test_duplicate_slug_ignores_case(client: TestClient, people):
    _create(client, slug="party")

    response = client.post(
        "/api/short-links",
        json={"slug": "PARTY", "target_url": "https://example.com"},
        headers=_as(ADMIN),
    )

    assert response.status_code == 409


def test_update_changes_slug_target_and_note_and_logs(
    client: TestClient, db: Session, people
):
    link = _create(client, note="old note")

    response = client.put(
        f"/api/short-links/{link['id']}",
        json={"slug": "Drive", "target_url": "https://example.org/new", "note": ""},
        headers=_as(ADMIN),
    )

    assert response.status_code == 200
    assert response.json()["slug"] == "drive"
    assert response.json()["target_url"] == "https://example.org/new"
    assert response.json()["note"] is None
    assert _audit(db, "short_link_updated").details == {
        "old_slug": "fundraiser",
        "slug": "drive",
        "old_target_url": "https://example.com/give",
        "target_url": "https://example.org/new",
        "old_note": "old note",
        "note": None,
    }


def test_update_keeping_its_own_slug_is_not_a_duplicate(client: TestClient, people):
    link = _create(client)

    response = client.put(
        f"/api/short-links/{link['id']}",
        json={"slug": "FUNDRAISER", "target_url": "https://example.com/other"},
        headers=_as(ADMIN),
    )

    assert response.status_code == 200


def test_update_to_another_links_slug_conflicts(client: TestClient, people):
    _create(client, slug="one")
    two = _create(client, slug="two")

    response = client.put(
        f"/api/short-links/{two['id']}",
        json={"slug": "One", "target_url": "https://example.com"},
        headers=_as(ADMIN),
    )

    assert response.status_code == 409


def test_delete_removes_and_logs(client: TestClient, db: Session, people):
    link = _create(client)

    response = client.delete(f"/api/short-links/{link['id']}", headers=_as(ADMIN))

    assert response.status_code == 204
    assert db.query(ShortLink).count() == 0
    entry = _audit(db, "short_link_deleted")
    assert entry.entity_id == link["id"]
    assert entry.details["target_url"] == "https://example.com/give"


def test_missing_link_is_404(client: TestClient, people):
    body = {"slug": "x", "target_url": "https://example.com"}
    assert (
        client.put("/api/short-links/99", json=body, headers=_as(ADMIN)).status_code == 404
    )
    assert client.delete("/api/short-links/99", headers=_as(ADMIN)).status_code == 404


@pytest.mark.parametrize("email", [PROMOTIONS, STAFF, INACTIVE, "stranger@example.com"])
def test_only_site_admins_can_manage(client: TestClient, people, email):
    link = _create(client)
    body = {"slug": "x", "target_url": "https://example.com"}

    assert client.get("/api/short-links", headers=_as(email)).status_code == 403
    assert client.post("/api/short-links", json=body, headers=_as(email)).status_code == 403
    assert (
        client.put(f"/api/short-links/{link['id']}", json=body, headers=_as(email))
    ).status_code == 403
    assert (
        client.delete(f"/api/short-links/{link['id']}", headers=_as(email))
    ).status_code == 403


# --- Redirects ---


@pytest.mark.parametrize("path", ["/go/fundraiser", "/go/FundRaiser", "/go/FUNDRAISER/"])
def test_redirect_ignores_case_and_trailing_slash(client: TestClient, people, path):
    _create(client)

    response = client.get(path, headers=_as(STAFF), follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/give"
    assert response.headers["cache-control"] == "no-store"


def test_redirect_follows_target_changes(client: TestClient, people):
    link = _create(client)
    client.put(
        f"/api/short-links/{link['id']}",
        json={"slug": "fundraiser", "target_url": "https://example.org/moved"},
        headers=_as(ADMIN),
    )

    response = client.get("/go/fundraiser", headers=_as(STAFF), follow_redirects=False)

    assert response.headers["location"] == "https://example.org/moved"


def test_redirect_drops_query_string(client: TestClient, people):
    _create(client)

    response = client.get(
        "/go/fundraiser?utm=x", headers=_as(STAFF), follow_redirects=False
    )

    assert response.headers["location"] == "https://example.com/give"


@pytest.mark.parametrize("path", ["/go/nope", "/go/", "/go/fundraiser/extra"])
def test_unknown_slug_is_a_404_page(client: TestClient, people, path):
    _create(client)

    response = client.get(path, headers=_as(STAFF), follow_redirects=False)

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == "no-store"


def test_unknown_slug_is_escaped_on_the_404_page(client: TestClient, people):
    response = client.get("/go/<script>", headers=_as(STAFF))

    assert "<script>" not in response.text
    assert "&lt;script&gt;" in response.text


@pytest.mark.parametrize(
    "headers",
    [
        {"X-DJ-Network": "1", "X-Forwarded-For": "192.168.1.100"},
        {"X-Station-Office-Network": "1", "X-Forwarded-For": "192.168.2.50"},
    ],
    ids=["dj-network", "station-office-network"],
)
def test_guests_must_sign_in(client: TestClient, people, headers):
    _create(client)

    response = client.get("/go/fundraiser", headers=headers, follow_redirects=False)

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("text/html")
    assert "example.com/give" not in response.text


@pytest.mark.parametrize("email", [INACTIVE, "stranger@example.com"])
def test_only_active_staff_can_follow(client: TestClient, people, email):
    _create(client)

    response = client.get("/go/fundraiser", headers=_as(email), follow_redirects=False)

    assert response.status_code == 403
    assert "example.com/give" not in response.text


def test_redirect_without_apache_layer_is_refused(client: TestClient, people):
    response = client.get("/go/fundraiser", follow_redirects=False)

    assert response.status_code == 400
